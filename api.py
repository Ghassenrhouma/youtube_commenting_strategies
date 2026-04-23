"""
FastAPI backend for the Comment Grid web app.
Runs inside each Docker container on port 8000.
Start with: uvicorn api:app --host 0.0.0.0 --port 8000
"""
import os
import subprocess
import signal
import psutil
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import gspread

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Constants ──────────────────────────────────────────────────────────────────

CONTAINER_NAME = os.getenv("CONTAINER_NAME", "unknown")  # set in docker-compose

PROFILE_PATHS = {
    "account1": os.getenv("PROFILE_ACCOUNT1", "/app/profiles/account1"),
    "account2": os.getenv("PROFILE_ACCOUNT2", "/app/profiles/account2"),
    "account3": os.getenv("PROFILE_ACCOUNT3", "/app/profiles/account3"),
}

# Maps (strategy, account) → the script filename
SCRIPT_MAP = {
    ("s1", "account1"): "s1_account1.py",
    ("s1", "account2"): "s1_account2.py",
    ("s1", "account3"): "s1_account3.py",
    ("s2", "account1"): "s2_account1.py",
    ("s2", "account2"): "s2_account2.py",
    ("s3", "account1"): "s3_account1.py",
    ("s3", "account2"): "s3_account2.py",
    ("s4", "account1"): "s4_account1.py",
}

STRATEGY_LABELS = {
    "s1": "Thread Building",
    "s2": "Depth Escalation",
    "s3": "Staged Disagreement",
    "s4": "Replayable Comment",
}

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH", "service_account.json")

# pid → {strategy, account, started_at, script}
_running: dict[int, dict] = {}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _check_profile(account: str) -> bool:
    """Return True if the profile folder exists (lightweight check, no browser launch)."""
    path = PROFILE_PATHS.get(account, "")
    return os.path.isdir(path)


def _profile_status(account: str) -> str:
    """active if profile folder exists, else needs_login."""
    return "active" if _check_profile(account) else "needs_login"


def _cleanup_dead():
    """Remove processes that have exited from the running registry."""
    dead = [pid for pid, _ in _running.items() if not psutil.pid_exists(pid)]
    for pid in dead:
        _running.pop(pid, None)


# ── Models ─────────────────────────────────────────────────────────────────────

class LaunchRequest(BaseModel):
    strategy: str   # "s1" | "s2" | "s3" | "s4"
    account: str    # "account1" | "account2" | "account3"
    dry_run: bool = False
    skip_delays: bool = False


class StopRequest(BaseModel):
    strategy: str
    account: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/status")
def get_status():
    """
    Returns container identity, all account profile states,
    and every currently running bot process.
    """
    _cleanup_dead()
    accounts = [
        {
            "id": account,
            "label": f"Account {account[-1]}",
            "profile_path": PROFILE_PATHS[account],
            "status": _profile_status(account),
        }
        for account in PROFILE_PATHS
    ]
    processes = [
        {
            "pid": pid,
            "strategy": info["strategy"],
            "account": info["account"],
            "script": info["script"],
            "started_at": info["started_at"],
            "uptime_s": int((datetime.now(timezone.utc) - datetime.fromisoformat(info["started_at"])).total_seconds()),
        }
        for pid, info in _running.items()
    ]
    return {
        "container": CONTAINER_NAME,
        "accounts": accounts,
        "running": processes,
    }


@app.post("/launch")
def launch(req: LaunchRequest):
    """Start a bot script for the given strategy + account."""
    _cleanup_dead()

    key = (req.strategy, req.account)
    script = SCRIPT_MAP.get(key)
    if not script:
        raise HTTPException(status_code=400, detail=f"No script for {req.strategy} / {req.account}")

    # Prevent duplicate — same strategy+account already running
    for pid, info in _running.items():
        if info["strategy"] == req.strategy and info["account"] == req.account:
            raise HTTPException(status_code=409, detail=f"Already running (pid {pid})")

    if not _check_profile(req.account):
        raise HTTPException(status_code=412, detail=f"Profile for {req.account} not found — run login.py first")

    script_path = os.path.join(os.path.dirname(__file__), script)
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Script not found: {script}")

    env = os.environ.copy()
    env["DRY_RUN"] = "true" if req.dry_run else "false"
    env["SKIP_DELAYS"] = "true" if req.skip_delays else "false"
    env["PROFILE_PATH"] = PROFILE_PATHS[req.account]

    proc = subprocess.Popen(
        ["python3", script_path],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    _running[proc.pid] = {
        "strategy": req.strategy,
        "account": req.account,
        "script": script,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    return {"pid": proc.pid, "script": script, "started": True}


@app.post("/stop")
def stop(req: StopRequest):
    """Stop all running processes for the given strategy + account."""
    _cleanup_dead()
    stopped = []
    for pid, info in list(_running.items()):
        if info["strategy"] == req.strategy and info["account"] == req.account:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except Exception:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            _running.pop(pid, None)
            stopped.append(pid)
    if not stopped:
        raise HTTPException(status_code=404, detail="No matching process found")
    return {"stopped_pids": stopped}


@app.get("/logs")
def get_logs(strategy: str = None, account: str = None, days: int = 14):
    """
    Pull rows from Google Sheet for the performance charts.
    Returns daily aggregates for the last N days.
    """
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
        if "reply" in role or "challenger" in role or "closer" in role or "replyable" in role:
            buckets[day_key]["replies"] += 1
        else:
            buckets[day_key]["comments"] += 1

    series = sorted(buckets.values(), key=lambda x: x["day"])
    totals = {
        "comments": sum(d["comments"] for d in series),
        "replies": sum(d["replies"] for d in series),
    }
    return {"series": series, "totals": totals, "container": CONTAINER_NAME}


@app.get("/health")
def health():
    return {"ok": True, "container": CONTAINER_NAME, "time": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
