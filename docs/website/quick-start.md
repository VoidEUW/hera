# Quick Start

The fastest way to run Hera: one Docker container on your own machine.

## Requirements

- Docker and Docker Compose
- A local OpenAI-compatible model endpoint (LM Studio, vLLM, llama.cpp) serving
  **Qwen3.6-35B**, reachable from the container

## Install

```bash
git clone https://github.com/VoidEUW/hera.git
cd hera
docker compose up --build
```

Open `http://localhost:8756`.

## Point Hera at your model

`docker-compose.yml` ships with two environment variables that seed the model endpoint the
first time the container starts:

```yaml
environment:
  HERA_PROVIDER_BASE_URL: "http://host.docker.internal:1234/v1"
  HERA_PROVIDER_MODEL: "qwen3.6-35b"
```

If your model endpoint runs on the same machine as Docker, `host.docker.internal` already
resolves to it — edit only the port and model name. You can also change the endpoint later
from Settings → Models in the interface; once that happens, the file on disk wins and these
variables are ignored.

## Data

Everything Hera keeps — chats, memory, mind, skills — lives in the `hera_data` Docker volume.

```bash
docker compose down        # stops the container, keeps the data
docker compose down -v     # also deletes the volume — irreversible
```

## Next

For a host-folder mount, building without Compose, or running from source instead of Docker,
see **Local Installation**. For every setting Hera reads, see **Configuration**.
