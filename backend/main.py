from fastapi import FastAPI, UploadFile, File, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from itertools import count
import numpy as np
import pandas as pd
from backend.llm.service import get_llm_response
from models.messages import ChatRequest
import dotenv

dotenv.load_dotenv()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
chat_counter = count(1)
chat_store = {}

def create_dataset_summary(df: pd.DataFrame):
    clean_preview = (
        preview_df = df.head(5).replace([np.nan, np.inf, -np.inf], None).to_dict(orient="records")
    )

    clean_describe = (
        df.describe(include="all").replace([np.nan, np.inf, -np.inf], None).to_dict()
    )

    return {
        "rows": len(df),
        "column_count": len(df.columns),
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "missing_values": df.isnull().sum().astype(int).to_dict(),
        "describe": clean_describe,
        "preview": clean_preview,
    }


@app.post("/chat")
def chat(request: ChatRequest):

    if request.chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")
    
    chat_store[request.chat_id], response = get_llm_response(
        chat_store[request.chat_id],
        message=request.message
    )
    
    return {
        "chat_id": request.chat_id,
        "response": response
    }


@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Nur CSV-Dateien sind erlaubt!")
    
    try:
        df = pd.read_csv(file.file)
    except Exception:
        raise HTTPException(status_code=400, detail="CSV-Datei konnte nicht gelesen werden.")
    
    chat_id = f"chat_{next(chat_counter)}"

    summary = create_dataset_summary(df)

    chat_store[chat_id] = {
        "filename": file.filename,
        "dataframe": df,
        "summary": summary,
        "messages": [],
        "plots": []
}
    
    preview_df = df.head(5).replace([np.nan, np.inf, -np.inf], None)
    
    # Let the model analyze the file
    return {
        "chat_id": chat_id,
        "filename": file.filename,
        "summary": summary
        }


@app.get("/plots/{chat_id}/{plot_index}")               # für einen einzelnen Plot
def get_plots(chat_id: str, plot_index: int):
    if chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")
    
    plots = chat_store[chat_id].get("plots", [])

    if plot_index < 1 or plot_index > len(plots):
        raise HTTPException(status_code=404, detail="Plot nicht gefunden.")
    
    svg = plots[plot_index - 1]["svg"]
    
    return Response(content=svg, media_type="image/svg+xml")

@app.get("/plots/{chat_id}")                            # für alle Plots pro Chat-ID
def get_plots(chat_id: str):
    if chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")

    return {
        "chat_id": chat_id,
        "plots": chat_store[chat_id].get("plots", [])
    }