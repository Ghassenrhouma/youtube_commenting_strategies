"""
FastAPI backend for the Comment Grid web app.
Runs inside each Docker container on port 8000.
Start with: uvicorn api:app --host 0.0.0.0 --port 8000
"""
import os
import subprocess
import signal
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CONTAINER_NAME = os.getenv("CONTAINER_NAME", "unknown")

# Scheduler script per strategy
SCHEDULER_MAP: dict[str, str] = {
    "s1": "run_s1_scheduler.py",
    "s2": "run_s2_scheduler.py",
    "s3": "run_s3_scheduler.py",
    "s4": "run_s4_scheduler.py",
}

# Expected number of accounts per strategy
STRATEGY_ROLES: dict[str, int] = {
    "s1": 3,
    "s2": 2,
    "s3": 2,
    "s4": 1,
}

# pid → {strategy, accounts, script, started_at}
_running: dict[int, dict] = {}


def _profile_path(account: str) -> str:
    return f"/app/profiles/{account}"


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _cleanup_dead():
    dead = [pid for pid in _running if not _pid_exists(pid)]
    for pid in dead:
        _running.pop(pid, None)


class LaunchRequest(BaseModel):
    strategy: str        # "s1" | "s2" | "s3" | "s4"
    accounts: list[str]  # ordered by role e.g. ["account4", "account7", "account9"]


class StopRequest(BaseModel):
    strategy: str


@app.get("/status")
def get_status():
    _cleanup_dead()
    processes = [
        {
            "pid": pid,
            "strategy": info["strategy"],
            "accounts": info["accounts"],
            "script": info["script"],
            "started_at": info["started_at"],
            "uptime_s": int((datetime.now(timezone.utc) - datetime.fromisoformat(info["started_at"])).total_seconds()),
        }
        for pid, info in _running.items()
    ]
    return {
        "container": CONTAINER_NAME,
        "running": processes,
    }


@app.post("/launch")
def launch(req: LaunchRequest):
    _cleanup_dead()

    expected = STRATEGY_ROLES.get(req.strategy)
    if expected is None:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy}")
    if len(req.accounts) != expected:
        raise HTTPException(status_code=400, detail=f"{req.strategy} requires {expected} account(s), got {len(req.accounts)}")

    # Prevent duplicate
    for pid, info in _running.items():
        if info["strategy"] == req.strategy:
            raise HTTPException(status_code=409, detail=f"{req.strategy} already running (pid {pid})")

    script = SCHEDULER_MAP[req.strategy]
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Scheduler not found: {script}")

    # Validate all profiles exist
    for account in req.accounts:
        profile = _profile_path(account)
        if not os.path.isdir(profile):
            raise HTTPException(status_code=412, detail=f"Profile not found: {profile} — run login.py first")

    # Pass accounts as PROFILE_ACCOUNT1, PROFILE_ACCOUNT2, PROFILE_ACCOUNT3
    env = os.environ.copy()
    for i, account in enumerate(req.accounts):
        env[f"PROFILE_ACCOUNT{i + 1}"] = _profile_path(account)

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{req.strategy}.log")

    log_file = open(log_path, "a")
    log_file.write(f"\n{'='*60}\n[API] Started {script} at {datetime.now(timezone.utc).isoformat()}\n")
    log_file.write(f"[API] Accounts: {req.accounts}\n{'='*60}\n")
    log_file.flush()

    proc = subprocess.Popen(
        ["python3", script_path],
        env=env,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
    )

    _running[proc.pid] = {
        "strategy": req.strategy,
        "accounts": req.accounts,
        "script": script,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "log": log_path,
    }

    return {"pid": proc.pid, "script": script, "accounts": req.accounts, "started": True, "log": log_path}


@app.post("/stop")
def stop(req: StopRequest):
    _cleanup_dead()
    stopped = []
    for pid, info in list(_running.items()):
        if info["strategy"] == req.strategy:
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


@app.get("/logs/{strategy}")
def get_log(strategy: str, lines: int = 50):
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", f"{strategy}.log")
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail=f"No log for {strategy} yet")
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"strategy": strategy, "lines": all_lines[-lines:]}


@app.get("/health")
def health():
    return {"ok": True, "container": CONTAINER_NAME, "time": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)