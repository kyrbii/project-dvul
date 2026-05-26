import pytest
from fastapi.testclient import TestClient
from backend.main import app
import io

client = TestClient(app)


# ── /upload-csv ──────────────────────────────────────────

def test_upload_csv_success():
    csv_content = b"name,age\nAlice,30\nBob,25"
    response = client.post(
        "/upload-csv",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    assert response.status_code == 200
    assert "chat_id" in response.json()


def test_upload_csv_wrong_format():
    response = client.post(
        "/upload-csv",
        files={"file": ("test.pdf", io.BytesIO(b"not a csv"), "application/pdf")}
    )
    assert response.status_code == 400


def test_upload_csv_empty_file():
    response = client.post(
        "/upload-csv",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    )
    assert response.status_code in [200, 400]


def test_upload_csv_invalid_content():
    response = client.post(
        "/upload-csv",
        files={"file": ("broken.csv", io.BytesIO(b"\x00\x01\x02"), "text/csv")}
    )
    assert response.status_code == 400


# ── /chat ─────────────────────────────────────────────────

def test_chat_invalid_chat_id():
    response = client.post(
        "/chat",
        json={"chat_id": "chat_999", "message": "Hallo"}
    )
    assert response.status_code == 404


def test_chat_success(mocker):
    # LLM mocken damit kein echter API Call gemacht wird
    mocker.patch(
        "backend.llm.service.get_llm_response",
        return_value=({"filename": "test.csv", "dataframe": None}, {"bot_message": "Antwort"})
    )

    # Erst CSV hochladen um chat_id zu bekommen
    csv_content = b"name,age\nAlice,30"
    upload = client.post(
        "/upload-csv",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    chat_id = upload.json()["chat_id"]

    # Dann Nachricht senden
    response = client.post(
        "/chat",
        json={"chat_id": chat_id, "message": "Analysiere die Daten"}
    )
    assert response.status_code == 200
    assert "response" in response.json()