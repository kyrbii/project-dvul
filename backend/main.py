from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import pandas as pd
from llm.service import get_response
import os
import dotenv

dotenv.load_dotenv()
import pandas as pd
import numpy as np

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
    
    preview_df = df.head(5).replace([np.nan, np.inf, -np.inf], None)
    
    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": df.columns.tolist(),
        "preview": preview_df.to_dict(orient="records")
    }