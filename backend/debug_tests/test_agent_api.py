from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app, chat_store


REFERENCE_FILE = Path(__file__).resolve().parents[2] / "test_data" / "StudentPerformanceFactors.csv"


@pytest.fixture
def client():
    """Provide a TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def uploaded_chat_id(client):
    """Upload the test CSV and return the chat_id."""
    if not REFERENCE_FILE.exists():
        pytest.skip(f"Reference file not found: {REFERENCE_FILE}")

    with REFERENCE_FILE.open("rb") as handle:
        response = client.post(
            "/upload-csv",
            files={"file": (REFERENCE_FILE.name, handle, "text/csv")},
        )

    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    chat_id = data.get("chat_id")
    assert chat_id, "Upload response did not return chat_id"
    return chat_id


def test_upload_csv(client):
    """Test that CSV upload succeeds and returns a valid chat_id."""
    if not REFERENCE_FILE.exists():
        pytest.skip(f"Reference file not found: {REFERENCE_FILE}")

    with REFERENCE_FILE.open("rb") as handle:
        response = client.post(
            "/upload-csv",
            files={"file": (REFERENCE_FILE.name, handle, "text/csv")},
        )

    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    assert "chat_id" in data
    assert "filename" in data
    assert "summary" in data


def test_chat_request(client, uploaded_chat_id):
    """Test that a chat request returns HTTP 200 and a non-empty response."""
    chat_payload = {
        "chat_id": uploaded_chat_id,
        "message": "Please generate a plot showing student performance distributions and any interesting correlations.",
    }

    response = client.post("/chat", json=chat_payload)
    assert response.status_code == 200, f"Chat request failed: {response.text}"

    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], dict)
    assert "bot_message" in data["response"]
    assert "plot_reference" in data["response"]
    assert data["response"]["bot_message"].strip(), "Chat response is empty"


def test_plot_generation(client, uploaded_chat_id):
    """Test that chat requests trigger plot generation and store them in the session."""
    chat_payload = {
        "chat_id": uploaded_chat_id,
        "message": "Please generate a plot showing student performance distributions and any interesting correlations.",
    }

    response = client.post("/chat", json=chat_payload)
    assert response.status_code == 200

    session = chat_store.get(uploaded_chat_id)
    assert session is not None, f"No session found for chat_id {uploaded_chat_id}"
    assert "plots" in session, "No plots were recorded in chat session"
    assert len(session["plots"]) > 0, "Plot generation was not triggered"

    # Verify plot structure
    for plot in session["plots"]:
        assert "title" in plot, "Plot missing 'title'"
        assert "svg" in plot, "Plot missing 'svg'"
        assert plot["svg"].strip(), "Plot SVG is empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])