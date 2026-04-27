from fastapi import FastAPI, UploadFile, File, HTTPException
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

    chat_store[chat_id] = {
        "filename": file.filename,
        "dataframe": df
    }
    
    preview_df = df.head(5).replace([np.nan, np.inf, -np.inf], None)
    
    # Let the model analyze the file
    return {
        "chat_id": chat_id
        }


@app.get("/plots/{chat_id}/{plot_index}")               # für einen einzelnen Plot
def get_plots(chat_id: str, plot_index: int):
    if chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")
    
    plots = chat_store[chat_id].get("plots", [])

    if plot_index < 1 or plot_index > len(plots):
        raise HTTPException(status_code=404, detail="Plot nicht gefunden.")
    
    return {
        "chat_id": chat_id,
        "plot_index": plot_index,
        "plot": plots[plot_index - 1]
    }

@app.get("/plots/{chat_id}")                            # für alle Plots pro Chat-ID
def get_plots(chat_id: str):
    if chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")

    return {
        "chat_id": chat_id,
        "plots": chat_store[chat_id].get("plots", [])
    }