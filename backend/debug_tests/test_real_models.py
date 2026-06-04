import logging
import dotenv
from models.model_selection import get_working_models

# Load environment variables
dotenv.load_dotenv()

# Setup logging to see warning details if models fail
logging.basicConfig(level=logging.INFO)

def test_working_models():
    print("Starting real model availability checks...")
    working_models = get_working_models(timeout=5.0)

    print("\n=== Active/Working Models ===")
    for model in working_models:
        print(f"✅ {model.short_name} (long_name: '{model.long_name}', local={model.local})")
    print("=============================")
    
    assert len(working_models) > 0, "No models are currently responsive or configured."
