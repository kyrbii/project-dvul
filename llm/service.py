from langchain_nvidia_ai_endpoints import ChatNVIDIA
import os
import dotenv
dotenv.load_dotenv()

def get_response(message: str) -> str:
    # Minimal Langchain integration point

    # TODO: Add API key to environment variables
    # TODO: Add model to environment variables
    # TODO: Add temperature to environment variables
    # TODO: Add top_p to environment variables
    # TODO: Add max_completion_tokens to environment variables
    # TODO: Add thinking mode to environment variables
    
    # define the API Client

    client = ChatNVIDIA(
      model=os.getenv("LLM_MODEL"),
      api_key= os.getenv("LLM_API_KEY"),
      temperature=1,
      top_p=1,
      max_completion_tokens=16384,
    )

    # get the response
    response = client.invoke([{"role":"user","content":message}])
      
    return response.content

