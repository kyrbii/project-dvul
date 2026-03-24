# project-dvul

see our documentation @ [Our Confluence](https://dvul.atlassian.net/wiki/spaces/dvul/overview)

## Running locally

### Using Docker (Recommended)
The easiest way to run the application securely is by using Docker Compose. Make sure Docker is installed on your system.

```bash
sudo docker compose up --build
```

- **Frontend Interface (Streamlit)**: [http://localhost:8501](http://localhost:8501)
- **Backend API & Docs (FastAPI)**: [http://localhost:8000/docs](http://localhost:8000/docs)


### Using `uv` Natively
If you prefer running natively without containers, ensure uv is installed

First, sync your environment:
```bash
uv sync
```

Then, open two separate terminals in the project root:

**Terminal 1 (Backend):**
```bash
uv run uvicorn backend.main:app --port 8000 --reload
```

**Terminal 2 (Frontend):**
```bash
API_URL=http://localhost:8000 uv run streamlit run frontend/app.py --server.port 8501
```
