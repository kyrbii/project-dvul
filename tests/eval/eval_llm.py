import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

SUPERSTORE_CSV = "test_data/superstore.csv"

# ── Hilfsfunktion ─────────────────────────────────────────


def upload_and_chat(csv_path: str, message: str) -> dict:
    with open(csv_path, "rb") as f:
        upload = client.post(
            "/upload-csv", files={"file": ("superstore.csv", f, "text/csv")}
        )
    assert upload.status_code == 200
    chat_id = upload.json()["chat_id"]

    response = client.post("/chat", json={"chat_id": chat_id, "message": message})
    assert response.status_code == 200
    return response.json()["response"]


# ── Bekannte Erkenntnisse aus Kaggle Notebooks ────────────
# Superstore Fakten:
# - Technology hat den höchsten Umsatz
# - Q4 hat den höchsten Umsatz
# - West Region hat den höchsten Profit
# - Furniture hat die niedrigste Profit-Margin


def test_llm_identifies_top_category():
    response = upload_and_chat(
        SUPERSTORE_CSV, "Welche Produktkategorie hat den höchsten Umsatz?"
    )
    assert response["bot_message"] != ""
    assert "technology" in response["bot_message"].lower()


def test_llm_generates_plot_for_category_question():
    response = upload_and_chat(
        SUPERSTORE_CSV, "Zeige mir den Umsatz pro Kategorie als Balkendiagramm"
    )
    assert len(response["plot_reference"]) > 0


def test_llm_identifies_best_region():
    response = upload_and_chat(SUPERSTORE_CSV, "Welche Region hat den höchsten Profit?")
    assert response["bot_message"] != ""
    assert "west" in response["bot_message"].lower()


def test_llm_identifies_trend():
    response = upload_and_chat(
        SUPERSTORE_CSV, "Wie hat sich der Umsatz über die Zeit entwickelt?"
    )
    assert response["bot_message"] != ""
    assert len(response["bot_message"]) > 100


def test_llm_generates_plot_for_trend():
    response = upload_and_chat(
        SUPERSTORE_CSV, "Zeige mir den Umsatztrend über die Zeit als Liniendiagramm"
    )
    assert len(response["plot_reference"]) > 0


def test_llm_response_is_not_empty():
    response = upload_and_chat(
        SUPERSTORE_CSV, "Fasse die wichtigsten Erkenntnisse zusammen"
    )
    assert response["bot_message"] != ""
    assert len(response["bot_message"]) > 50


def test_llm_identifies_low_margin_category():
    response = upload_and_chat(
        SUPERSTORE_CSV, "Welche Kategorie hat die niedrigste Profit-Margin?"
    )
    assert "furniture" in response["bot_message"].lower()


def test_llm_generates_multiple_plots():
    response = upload_and_chat(
        SUPERSTORE_CSV, "Zeige mir drei verschiedene Visualisierungen des Datensatzes"
    )
    assert len(response["plot_reference"]) >= 2


def test_llm_explains_plot():
    response = upload_and_chat(
        SUPERSTORE_CSV, "Erstelle einen Plot und erkläre was er zeigt"
    )
    assert len(response["plot_reference"]) > 0
    assert len(response["bot_message"]) > 50
