from fastapi import FastAPI, UploadFile, File, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from itertools import count
import numpy as np
import pandas as pd
from backend.llm.service import get_llm_response
from backend.logging_config import setup_logging, get_backend_logger
from models.messages import ChatRequest
import csv

setup_logging()
logger = get_backend_logger()

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

def detect_delimiter(file):
    sample = file.read(1024).decode("utf-8")
    file.seek(0)
    dialect = csv.Sniffer().sniff(sample)
    return dialect.delimiter

def has_header(file):
    sample = file.read(1024).decode("utf-8")
    file.seek(0)
    return csv.Sniffer().has_header(sample)

def create_dataset_summary(df: pd.DataFrame):
    clean_preview = (
        df.head(5).replace([np.nan, np.inf, -np.inf], None).to_dict(orient="records")
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
        # # delimiter erkennen
        #  delimiter = detect_delimiter(file.file)

        # # header erkennen 
        # header_exists = has_header(file.file)
        # 
        # if header_exists:
        #    df = pd.read_csv(file.file, delimiter=delimiter)
        # else:
        #    df = pd.read_csv(file.file, delimiter=delimiter, header=None)

        df = pd.read_csv(file.file)

    except Exception as e:
        logger.exception("CSV Fehler beim Einlesen der Datei")
        raise HTTPException(
            status_code=400,
            detail=f"CSV-Datei konnte nicht gelesen werden: {str(e)}"
        )
    
    chat_id = f"chat_{next(chat_counter)}" 

    summary = create_dataset_summary(df)

    chat_store[chat_id] = {             # @Korbi du musst dann in der get_llm_repsonse auch die summary miteinbeziehen fürs LLM
        "filename": file.filename,
        "dataframe": df# ,
        # "summary": summary,
        # "messages": [],
        # "plots": []
}
    
    preview_df = df.head(5).replace([np.nan, np.inf, -np.inf], None)
    
    # Let the model analyze the file
    return {
        "chat_id": chat_id,
        "filename": file.filename,
        "summary": summary
        }

@app.get("/description/{chat_id}")
def get_description(chat_id: str):
    if chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")
    
    return {
        "chat_id": chat_id,
        "summary": chat_store[chat_id]["description"]
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