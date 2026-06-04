# Data Visualisation and understanding with LLMs (DVUL)
Create your own plots and detailed descriptions for your csv datasets with an LLM.

---
### Visual to come
---
## Features
- **Heavily specialized in creating plots**: This tools main objective is to provide the user with the best possible plots for a given use case and data set.
- **Understand large data sets with ease**: With a detailed description, analysis and plots you are able to understand an unknown dataset at blazing speeds without having to take a single look into the data.
---
## Tech Stack
- **Frontend**: Angular, TypeScript, node.js
- **Backend**: FastAPI, Python, LangChain
- **Deployment**: Docker
---
## Prerequisites
- Latest version of `uv` by Astral.
- npm
- Docker Engine
- Docker Compose
---
## Installation & Setup
Clone the repository.

### Developing & Testing

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

### Production
The easiest way to run the application securely is by using Docker Compose. Make sure Docker is installed on your system. This uses the latest Release of the GitHub Repository.

```bash
sudo docker compose -f docker-compose.prod.yml up
```

### Plot sandbox container
The plot sandbox runs each generated plot execution in a one-shot container. Build the sandbox image once and let the backend invoke it on demand:

```bash
docker build -f Dockerfile.sandbox -t project_dvul_plot_sandbox:latest .
```

The backend uses the image name from `PLOT_SANDBOX_IMAGE`, defaulting to `project_dvul_plot_sandbox:latest`.

If the backend itself runs inside Docker with `docker-compose`, the backend container must be able to access the Docker daemon (for example by mounting `/var/run/docker.sock`).
