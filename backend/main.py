from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from llm.service import get_response
import pandas as pd

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat(request: ChatRequest):
    return {"response": get_response(request.message)}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Nur CSV-Dateien sind erlaubt!")
    
    try:
        df = pd.read_csv(file.file)
    except Exception:
        raise HTTPException(status_code=400, detail="CSV-Datei konnte nicht gelesen werden.")
    
    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": df.columns.tolist(),
        "preview": df.head(5).to_dict(orient="records")
    }