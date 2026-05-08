# Hackathon Submission Checklist

## Team

- **Team Number:** RVCE_BATISTA
- **College:** RV College of Engineering
- **Team Name:** Batista
- **Project:** LobCut

## Repository Contents

| Requirement | File / Folder | Notes |
|---|---|---|
| Complete source code | `python-service/`, `dashboard/`, `electron-app/`, `telegram-bot/`, `tests/` | Main project implementation |
| README | `README.md` | Problem, solution, setup, usage, and runtime model notes |
| AI disclosure | `OpenClaw_AI_Disclosure.docx` | Approved disclosure document |
| PPT | `RVCE_BATISTA_LobCut.pptx` | Final presentation deck |
| Demo video | `RVCE_BATISTA_DEMO.mov` | Project walkthrough video |
| Demo video backup | https://drive.google.com/file/d/1B_zX9koiEQngi_JmIXTDf1rL4iaOJt_d/view?usp=sharing | Backup link for evaluators |
| APK / SDK | Not applicable | LobCut is a local service + dashboard/desktop prototype |

## Demo Video Note

`RVCE_BATISTA_DEMO.mov` is the final demo export. Push it with Git LFS. The Drive link above is included as a backup in case the platform has trouble previewing the large file.

## Quick Run

```powershell
docker compose up --build
```

Then open:

```text
http://localhost:8000/health
```

For dashboard development:

```powershell
cd dashboard
npm install
npm run dev
```

For the desktop wrapper:

```powershell
cd electron-app
npm install
npm start
```

## Evaluation Flow

1. Start the backend with Docker Compose.
2. Open the dashboard or Electron app.
3. Drop media into the watched folders or call the API directly.
4. Review job status in the dashboard/API.
5. Check processed outputs under `output/images/` and `output/videos/`.

## Important Local Requirements

- FFmpeg must be installed for video, reel, and caption processing.
- Gemini features need a valid `GEMINI_API_KEY` in `.env`.
- Telegram features need `TELEGRAM_BOT_TOKEN` in `.env`.
- `.env` is intentionally not committed.
