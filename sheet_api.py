"""
Lightweight Google Sheet reader — runs on the HOST machine (not in Docker).
Serves performance data to the frontend on port 8000.
Start with: python sheet_api.py
"""
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import gspread

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH", "service_account.json")

STRATEGY_LABELS = {
    "s1": "Thread Building",
    "s2": "Depth Escalation",
    "s3": "Staged Disagreement",
    "s4": "Replayable Comment",
}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/logs")
def get_logs(strategy: str = None, account: str = None, days: int = 14):
    if not GOOGLE_SHEET_ID:
        raise HTTPException(status_code=503, detail="GOOGLE_SHEET_ID not configured")
    try:
        client = gspread.service_account(filename=SERVICE_ACCOUNT_PATH)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        rows = sheet.get_all_values()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Sheet error: {e}")

    # Sheet columns: timestamp | strategy | account | video_id | video_link | role | comment_id
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    buckets: dict[str, dict] = {}

    for row in rows[1:]:
        if len(row) < 3:
            continue
        try:
            ts = datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts < cutoff:
            continue
        if strategy and row[1] != STRATEGY_LABELS.get(strategy, strategy):
            continue
        if account and row[2] != f"Account {account[-1]}":
            continue

        day_key = ts.strftime("%Y-%m-%d")
        if day_key not in buckets:
            buckets[day_key] = {"day": day_key, "comments": 0, "replies": 0}
        role = row[5].lower() if len(row) > 5 else ""
        if any(k in role for k in ("reply", "challenger", "closer", "replyable")):
            buckets[day_key]["replies"] += 1
        else:
            buckets[day_key]["comments"] += 1

    series = sorted(buckets.values(), key=lambda x: x["day"])
    totals = {
        "comments": sum(d["comments"] for d in series),
        "replies": sum(d["replies"] for d in series),
    }
    return {"series": series, "totals": totals}


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("sheet_api:app", host="0.0.0.0", port=8000, reload=False)