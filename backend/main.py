from fastapi import FastAPI, UploadFile, File, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from itertools import count
import numpy as np
import pandas as pd
from backend.llm.service import get_llm_response
from backend.logging_config import setup_logging, get_backend_logger
from models.messages import ChatRequest
from models.model_selection import get_working_models
import csv
import threading
import asyncio
import dotenv

dotenv.load_dotenv()

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
model_store = []
is_startup_evaluated = False

def run_startup_evaluation():
    global model_store, is_startup_evaluated
    logger.info("Evaluating working models at startup in background...")
    try:
        working = get_working_models()
        if working:
            model_store = working
            logger.info(f"Loaded active models: {[m.short_name for m in model_store]}")
        else:
            logger.warning("No working models found during startup evaluation.")
    except Exception as e:
        logger.exception("Failed to evaluate models at startup", e)
    finally:
        is_startup_evaluated = True

@app.on_event("startup")
def startup_event():
    threading.Thread(target=run_startup_evaluation, daemon=True).start()

MAX_ACTIVITY_EVENTS = 50

def add_activity_event(chat_id: str, message: str, event_type: str = "agent") -> None:
    if chat_id not in chat_store:
        return

    next_index = chat_store[chat_id].setdefault("_activity_next_index", 1)
    activity = chat_store[chat_id].setdefault("activity", [])
    activity.append({
        "index": next_index,
        "type": event_type,
        "message": message,
    })
    chat_store[chat_id]["_activity_next_index"] = next_index + 1

    if len(activity) > MAX_ACTIVITY_EVENTS:
        chat_store[chat_id]["activity"] = activity[-MAX_ACTIVITY_EVENTS:]

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

    chat_store[request.chat_id]["activity"] = []
    add_activity_event(request.chat_id, "Analyse wird gestartet", "agent")
    model_name = request.model_name
    local = None
    default = True
    for model in model_store:
        if model.long_name == model_name:
            local = model.local 
            default = False
            break
    if default:
        model_name = "nvidia/nemotron-3-super-120b-a12b:free"
        local = False
    chat_store[request.chat_id], response = get_llm_response(
        chat_store[request.chat_id],
        message=request.message,
        model=model_name,
        local=local
    )
    add_activity_event(request.chat_id, "Antwort wurde erstellt", "agent")
    
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
        "dataframe": df,
        "activity": [],
        "_activity_next_index": 1,
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

@app.get("/activity/{chat_id}")
def get_activity(chat_id: str):
    if chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")

    return {
        "chat_id": chat_id,
        "activity": chat_store[chat_id].get("activity", [])
    }

@app.get("/description/{chat_id}")
def get_description(chat_id: str):
    if chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")
    
    description = chat_store[chat_id].get("description")
    if description is None:
        description = "Dataset description is not available"
        logger.warning(f"Description not found for chat_id {chat_id}")
    return {
        "chat_id": chat_id,
        "summary": description
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


@app.get("/models")
async def get_active_models():
    """
    Returns the list of active/working models. Waits until evaluation completes.
    """
    global is_startup_evaluated, model_store
    
    # Wait up to 15 seconds (30 * 0.5s) for the background check to complete
    for _ in range(30):
        if is_startup_evaluated:
            break
        await asyncio.sleep(0.5)
    return {"models": model_store}

