---
interval: 10s
channel: telegram
---

Every 10 seconds:
1. Fetch http://localhost:8000/jobs
2. Compare each job status against memory/lobcut-jobs.md
3. For status changes send Telegram notification:
   - PROCESSING: job started message
   - DONE: full result with category, tags, summary
   - FAILED: failure reason
4. Update memory/lobcut-jobs.md with current states
