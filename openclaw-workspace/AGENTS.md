# LobCut Agent Workspace

The LobCut API runs at `http://api:8000` inside Docker Compose and at
`http://localhost:8000` from the host. Use the `media-processor` skill for image
and video processing.

## Endpoints

- `POST /process/image`
- `POST /process/video`
- `GET /jobs`
- `GET /health`

## Rules

- Report only pipeline results.
- Do not expose API keys.
- Confirm before bulk-processing more than 10 files.
- Use `MEMORY_LOG.md` for recall questions.
