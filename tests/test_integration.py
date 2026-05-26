import io
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_full_flow(mocker):
    mocker.patch(
        "backend.llm.service.get_llm_response",
        return_value=(
            {"filename": "test.csv", "dataframe": None},
            {"bot_message": "Die Daten zeigen einen Trend"}
        )
    )

    # Schritt 1: CSV hochladen
    csv_content = b"name,age\nAlice,30\nBob,25"
    upload = client.post(
        "/upload-csv",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    assert upload.status_code == 200
    chat_id = upload.json()["chat_id"]

    # Schritt 2: Nachricht senden
    response = client.post(
        "/chat",
        json={"chat_id": chat_id, "message": "Analysiere die Daten"}
    )
    assert response.status_code == 200
    assert "response" in response.json()