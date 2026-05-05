# project-dvul

## Testing

First, bring your environment up to speed:
```bash
uv sync
cd frontend
npm install --legacy-peer-deps
cd ..
```

**Start the Backend:**
Terminal 1

```bash
uv run uvicorn backend.main:app --port 8000 --reload
```

**Start the Frontend:**
Terminal 2

```bash
cd frontend
npm start
```
**Open the App:**
[Frontend in the Web](http://localhost:4200)


## Running locally
### Using Docker (Recommended)
The easiest way to run the application securely is by using Docker Compose. Make sure Docker is installed on your system.

```bash
sudo docker compose -f docker-compose.prod.yml up
```

 **Backend API & Docs (FastAPI)**: [Swagger UI](http://localhost:8000/docs)