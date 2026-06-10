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


def test_csv_preview_is_limited_to_two_rows():
    csv_content = b"name,age\nAlice,30\nBob,25\nCharlie,35"
    upload = client.post(
        "/upload-csv",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    assert upload.status_code == 200
    upload_body = upload.json()
    assert len(upload_body["summary"]["preview"]) == 2

    chats = client.get("/chats")
    assert chats.status_code == 200
    uploaded_chat = next(
        chat for chat in chats.json()["chats"]
        if chat["chat_id"] == upload_body["chat_id"]
    )
    assert len(uploaded_chat["csv_preview"]["rows"]) == 2


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


# ── /chats and /chat/{chat_id}/history ──────────────────────

def test_get_chats():
    response = client.get("/chats")
    assert response.status_code == 200
    assert "chats" in response.json()


def test_get_chat_history_not_found():
    response = client.get("/chat/chat_9999/history")
    assert response.status_code == 404


def test_get_chat_history_success():
    csv_content = b"name,age\nAlice,30"
    upload = client.post(
        "/upload-csv",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    chat_id = upload.json()["chat_id"]

    response = client.get(f"/chat/{chat_id}/history")
    assert response.status_code == 200
    assert response.json()["chat_id"] == chat_id
    assert isinstance(response.json()["messages"], list)
