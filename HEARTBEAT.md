# MediaScribe — Daily Heartbeat

## Instructions for Agent
Every morning at 08:00, read MEMORY_LOG.md and post a daily digest to Telegram.
Format the digest exactly as shown below. If no files were processed yesterday,
say so briefly and sign off.

---

## Digest Template

**📊 MediaScribe Daily Digest — {DATE}**

**Yesterday's Activity:**
- 🖼️ Images processed: {IMAGE_COUNT}
- 🎬 Videos processed: {VIDEO_COUNT}
- 📁 Total jobs: {TOTAL_COUNT}

**Top Categories (Images):**
{LIST TOP 3 CATEGORIES WITH COUNTS}

**Videos Transcribed:**
{LIST VIDEO FILENAMES AND DURATION}

**Notable Finds:**
{ANY UNUSUAL CATEGORIES OR HIGH-CONFIDENCE CLASSIFICATIONS WORTH HIGHLIGHTING}

**System Status:**
- Python service: {check GET http://localhost:8000/health}
- DB jobs today: {TOTAL_COUNT}

---
*MediaScribe is running on your local machine. Send a file path to process new media.*
