# Docker Installation

Hera ships a `Dockerfile` and a `docker-compose.yml`. The image builds the web interface and
the server into one image and runs the server only.

## Requirements

- Docker and Docker Compose
- A local OpenAI-compatible model endpoint (LM Studio, vLLM, llama.cpp) serving
  **Qwen3.6-35B**, reachable from the container

## Run with Docker Compose

```bash
git clone https://github.com/VoidEUW/hera.git
cd hera
docker compose up --build
```

Open `http://localhost:8756`.

## What the compose file does

- Builds the image from the repository's `Dockerfile`.
- Publishes port `8756`.
- Stores all data in a named volume, `hera_data`, mounted at `/data`. A named volume avoids
  the file-permission mismatches a bind mount runs into on macOS and Windows.
- Sets `HERA_HOME=/data` and `HERA_HOST=0.0.0.0`, so the server writes into the volume and is
  reachable from outside the container.
- Adds `host.docker.internal:host-gateway`, so the container can reach a model endpoint
  running on the host machine.

## Configuring the model endpoint

Two environment variables seed the model configuration the first time the container starts:

| Variable | Purpose | Example |
|---|---|---|
| `HERA_PROVIDER_BASE_URL` | The model endpoint | `http://host.docker.internal:1234/v1` |
| `HERA_PROVIDER_MODEL` | The model name | `qwen3.6-35b` |

These only take effect on first run. Once `~/.hera/config.toml` exists inside the volume, the
file wins, and changing these variables later has no effect — change the model from the
Settings screen instead. See **Configuration** for every setting Hera reads.

If your model endpoint runs on the same machine as Docker, use `host.docker.internal` in
`HERA_PROVIDER_BASE_URL`, as in the example above. It resolves automatically on Docker Desktop
(macOS, Windows); the `extra_hosts` entry in the compose file is what makes it resolve on
Linux too.

## Using a host folder instead of a named volume

By default, data lives in the `hera_data` volume, not a folder you can browse directly. To use
a folder instead — useful since `mind/` is a real git repository and `memories/` is one
markdown file per memory, both meant to be opened outside Hera too — replace the volume line
in `docker-compose.yml`:

```yaml
volumes:
  - ${HOME}/.hera:/data
```

The container writes as root. On Docker Desktop (macOS, Windows) this is mapped back to your
user automatically. On native Linux, files land root-owned until you also add
`user: "${UID}:${GID}"` to the service, with `UID` and `GID` exported from your shell.

## Persisting and resetting data

All data lives in the `hera_data` volume. Removing the container does not remove the volume:

```bash
docker compose down        # stops and removes the container, keeps data
docker compose down -v     # also deletes the volume — irreversible
```

## Building without Compose

```bash
docker build -t hera .
docker run -p 8756:8756 \
  -v hera_data:/data \
  -e HERA_PROVIDER_BASE_URL=http://host.docker.internal:1234/v1 \
  -e HERA_PROVIDER_MODEL=qwen3.6-35b \
  --add-host=host.docker.internal:host-gateway \
  hera
```
