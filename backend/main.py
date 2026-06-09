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
CSV_PREVIEW_ROW_LIMIT = 2

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
        df.head(CSV_PREVIEW_ROW_LIMIT)
        .replace([np.nan, np.inf, -np.inf], None)
        .to_dict(orient="records")
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

def create_csv_preview(file_name: str, summary: dict):
    return {
        "fileName": file_name,
        "headers": summary["columns"],
        "rows": [
            [str(row.get(col, "")) for col in summary["columns"]]
            for row in summary["preview"]
        ],
    }


@app.post("/chat")
def chat(request: ChatRequest):

    if request.chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")

    chat_store[request.chat_id]["activity"] = []
    add_activity_event(request.chat_id, "Analyse wird gestartet", "agent")
    chat_store[request.chat_id]["status"] = "running"
    
    model_name = request.model_name
    local = None
    default = True
    for model in model_store:
        if model.long_name == model_name:
            local = model.local 
            default = False
            break
    if default:
        model_name = "openai/gpt-oss-120b:free"
        local = False

    try:
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
    except Exception as e:
        add_activity_event(request.chat_id, f"Fehler bei der Analyse: {str(e)}", "agent")
        add_activity_event(request.chat_id, "Antwort wurde erstellt", "agent")
        raise e
    finally:
        chat_store[request.chat_id]["status"] = "idle"


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

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV-Datei enthält keine verwertbaren Daten.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("CSV Fehler beim Einlesen der Datei")
        raise HTTPException(
            status_code=400,
            detail=f"CSV-Datei konnte nicht gelesen werden: {str(e)}"
        )
    
    chat_id = f"chat_{next(chat_counter)}" 

    summary = create_dataset_summary(df)

    from datetime import datetime
    created_at = datetime.now().strftime("%d.%m.%Y, %H:%M")
    chat_name = file.filename.replace('.csv', '')
    csv_preview = create_csv_preview(file.filename, summary)
    chat_store[chat_id] = {
        "filename": file.filename,
        "dataframe": df,
        "activity": [],
        "_activity_next_index": 1,
        "messages": [],
        "plots": [],
        "created_at": created_at,
        "name": chat_name,
        "csv_preview": csv_preview
    }

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


@app.get("/chats")
def get_chats():
    from datetime import datetime
    chats_list = []
    for chat_id, chat_data in chat_store.items():
        messages = chat_data.get("messages", [])
        plots = []
        for idx, p in enumerate(chat_data.get("plots", []), 1):
            plots.append({
                "title": p.get("title", f"Plot {idx}"),
                "svg": p.get("svg")
            })
            
        csv_preview = chat_data.get("csv_preview")
        if not csv_preview and "dataframe" in chat_data:
            df = chat_data["dataframe"]
            summary = create_dataset_summary(df)
            csv_preview = create_csv_preview(
                chat_data.get("filename", "dataset.csv"),
                summary,
            )
            chat_data["csv_preview"] = csv_preview

        chats_list.append({
            "chat_id": chat_id,
            "name": chat_data.get("name", chat_data.get("filename", chat_id).replace('.csv', '')),
            "uploaded_filename": chat_data.get("filename"),
            "description": chat_data.get("description"),
            "messages": messages,
            "plots": plots,
            "csv_preview": csv_preview,
            "created_at": chat_data.get("created_at", datetime.now().strftime("%d.%m.%Y, %H:%M")),
            "status": chat_data.get("status", "idle")
        })
    return {"chats": chats_list}


@app.get("/chat/{chat_id}/history")
def get_chat_history(chat_id: str):
    if chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden.")
    return {
        "chat_id": chat_id,
        "messages": chat_store[chat_id].get("messages", [])
    }
