# Data Visualisation and understanding with LLMs (DVUL)

Create your own plots and detailed descriptions for your CSV datasets with an LLM.

---

## Features
- **Specialized Plot Generation**: Automatically produces visual diagrams for uploaded datasets via Matplotlib, Seaborn, and Pandas.
- **Natural Language Analyst**: A ReAct agent runs queries, calculates correlations, reviews distributions, and describes columns.
- **Agent Activity Log**: Real-time display of agent tools and parameters in the frontend.
- **Self-Correcting Plot Loop**: Uses a LangGraph cycle to write, validate, and self-repair plotting scripts.
- **Multi-Model Support**: Use local models (Ollama) or remote endpoints (OpenRouter).

---

## Architecture & System Flow

The system runs as an Angular client talking to a FastAPI server that coordinates two LLM agents:

1. **Frontend (Angular)**: The user interface defined in [app.component.ts](frontend/src/app/app.component.ts) and [chat.service.ts](frontend/src/app/chat.service.ts).
2. **Backend (FastAPI)**: Manages routing, state, and files. Defined in [main.py](backend/main.py).
3. **Analyst Agent**: A ReAct agent that utilizes analytical tools to query the dataset. Defined in [agent_connection.py](backend/llm/agent_connection.py) and [tools.py](backend/llm/tools.py).
4. **Plotting Agent**: A specialized LangGraph sub-graph that generates code and corrects execution errors dynamically. Defined in [plot_agent.py](backend/llm/plot_agent.py).
5. **Hardened Sandbox**: Executes plotting code in a restricted scope with disabled builtins, producing SVG assets. Defined in [sandbox.py](backend/llm/sandbox.py).

---

## Installation & Setup

### Production (Using Docker)

To run the application using pre-built images pulled directly from the GitHub Container Registry (GHCR):

1. **Prerequisites**: Ensure you have **Docker** and **Docker Compose** installed.
2. **Environment File**: Create a `.env` file in the root workspace directory with your credentials:
   ```ini
   # Remote OpenRouter Config
   OPENROUTER_API_KEY="sk-or-v1-your-key-here"
   OPENROUTER_MODEL="openai/gpt-oss-120b:free"
   ```
3. **Launch Service**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
   *The application is served at `http://localhost:4200`.*

---

### Local Development

For running and modifying the codebase locally:

1. **Prerequisites**: Ensure you have **npm**, **Docker** (optional, for local compose builds), and **uv** (by Astral) installed.
2. **Environment Setup**: Create a `.env` file in the root workspace directory:
   ```ini
   # Remote OpenRouter Config
   OPENROUTER_API_KEY="sk-or-v1-your-key-here"
   OPENROUTER_MODEL="openai/gpt-oss-120b:free"

   # Local Ollama Config (Optional)
   OLLAMA_MODEL="gemma4"
   # OLLAMA_HOST="http://localhost:11434"

   # Configuration & Logging
   LOG_LEVEL="DEBUG"
   LOG_FILE="logs/backend.log"
   ```
3. **Sync Dependencies**:
   ```bash
   uv sync
   cd frontend && npm install --legacy-peer-deps && cd ..
   ```
4. **Start Backend**:
   ```bash
   uv run uvicorn backend.main:app --port 8000 --reload
   ```
5. **Start Frontend**:
   ```bash
   cd frontend && npm start
   ```
   *The app runs at `http://localhost:4200`.*
6. **Optional (Local Docker Container Build with backend volume mounts)**:
   ```bash
   docker compose up --build
   ```
