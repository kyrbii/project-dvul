from fastapi import FastAPI
from pydantic import BaseModel
from llm.service import get_response
import os
import dotenv

dotenv.load_dotenv()

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat(request: ChatRequest):
    return {"response": get_response(request.message)}
