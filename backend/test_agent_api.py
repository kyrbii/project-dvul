from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd
from itertools import count

# Import the new agent logic
from backend.llm.agent_connection import agent_call
from models.messages import ChatRequest

app = FastAPI(title="Agent Test API")

# Setup state (similar to main.py)
chat_counter = count(1)
chat_store = {}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed.")
    
    try:
        df = pd.read_csv(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {str(e)}")
    
    chat_id = f"test_chat_{next(chat_counter)}"
    
    # Store the dataframe for the agent
    chat_store[chat_id] = {
        "filename": file.filename,
        "dataframe": df
    }
    
    return {
        "chat_id": chat_id,
        "message": "File uploaded successfully. You can now chat using this chat_id.",
        "columns": list(df.columns),
        "rows": len(df)
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    if not request.chat_id or request.chat_id not in chat_store:
        raise HTTPException(status_code=404, detail="Chat ID not found. Please upload a CSV first.")
    
    # Call our new agent logic
    # Note: agent_call returns (updated_chat_store, bot_message)
    chat_store[request.chat_id], response_text = agent_call(
        chat_store[request.chat_id], 
        message=request.message,
        max_iterations=10 # Allowing more tries for testing
    )
    
    return {
        "chat_id": request.chat_id,
        "response": response_text
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
