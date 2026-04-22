import json
import os
import time
from datetime import datetime, timedelta
from filelock import FileLock

_DIR = os.path.dirname(os.path.abspath(__file__))  # noqa
S1_FILE = os.path.join(_DIR, "targets_s1.json")
S2_FILE = os.path.join(_DIR, "targets_s2.json")
S3_FILE = os.path.join(_DIR, "targets_s3.json")
PAIRS_FILE = os.path.join(_DIR, "used_pairs_s3.json")

TOPIC_PAIRS_S3 = [
    "air freight vs sea freight",
    "FOB vs DDP",
    "direct import vs middleman",
    "Amazon FBA vs 3PL warehouse",
    "express courier vs ocean consolidation",
    "EXW vs CIF",
    "DHL Express vs freight forwarder",
    "supplier audit vs skip audit",
    "bonded warehouse vs direct delivery",
    "sea LCL vs sea FCL",
    "sourcing agent vs direct factory",
    "prepayment vs letter of credit",
]


def sleep_if_night():
    while 0 <= datetime.now().hour < 8:
        print("[NIGHT BLOCK] Sleeping — resumes at 08:00...")
        time.sleep(300)


def _read(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path: str, data: list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class _Lock:
    """FileLock wrapper that falls back to a no-op on CIFS/Windows mounts where locking fails."""
    def __init__(self, path: str):
        self._path = path
        self._lock = None
        try:
            self._lock = FileLock(path, timeout=10)
        except Exception:
            pass

    def __enter__(self):
        if self._lock:
            try:
                self._lock.acquire()
            except Exception:
                self._lock = None
        return self

    def __exit__(self, *args):
        if self._lock:
            try:
                self._lock.release()
            except Exception:
                pass


# ── Strategy 1 ────────────────────────────────────────────────────────────────

def s1_add_target(video_id: str, video_title: str):
    lock = _Lock(S1_FILE + ".lock")
    with lock:
        data = _read(S1_FILE)
        if not any(t["video_id"] == video_id for t in data):
            data.append({
                "video_id": video_id,
                "video_title": video_title,
                "status": "pending",
                "account1_comment_id": "",
                "account1_comment_text": "",
                "account2_comment_id": "",
                "account2_comment_text": "",
                "account3_comment_id": "",
                "a_posted_at": "",
                "b_posted_at": "",
            })
            _write(S1_FILE, data)
            print(f"[S1] Added target: {video_id} — {video_title[:50]}")


def s1_get_pending() -> dict | None:
    lock = _Lock(S1_FILE + ".lock")
    with lock:
        for t in _read(S1_FILE):
            if t["status"] == "pending":
                return t
    return None


def s1_get_a_done_ready(skip_delays: bool = False) -> dict | None:
    lock = _Lock(S1_FILE + ".lock")
    with lock:
        now = datetime.utcnow()
        for t in _read(S1_FILE):
            if t["status"] != "a_done":
                continue
            if skip_delays:
                return t
            posted = t.get("a_posted_at", "")
            if not posted:
                return t
            try:
                elapsed_min = (now - datetime.fromisoformat(posted)).total_seconds() / 60
                if elapsed_min >= 20:
                    return t
            except Exception:
                return t
    return None


def s1_get_b_done_ready(skip_delays: bool = False) -> dict | None:
    lock = _Lock(S1_FILE + ".lock")
    with lock:
        now = datetime.utcnow()
        for t in _read(S1_FILE):
            if t["status"] != "b_done":
                continue
            if skip_delays:
                return t
            posted = t.get("b_posted_at", "")
            if not posted:
                return t
            try:
                elapsed_min = (now - datetime.fromisoformat(posted)).total_seconds() / 60
                if elapsed_min >= 20:
                    return t
            except Exception:
                return t
    return None


def s1_update(video_id: str, **kwargs):
    lock = _Lock(S1_FILE + ".lock")
    with lock:
        data = _read(S1_FILE)
        for t in data:
            if t["video_id"] == video_id:
                t.update(kwargs)
                break
        _write(S1_FILE, data)


def s1_get_all_ids() -> set:
    lock = _Lock(S1_FILE + ".lock")
    with lock:
        return {t["video_id"] for t in _read(S1_FILE)}


# ── Strategy 2 ────────────────────────────────────────────────────────────────

def s2_add_target(video_id: str, video_title: str):
    lock = _Lock(S2_FILE + ".lock")
    with lock:
        data = _read(S2_FILE)
        if not any(t["video_id"] == video_id for t in data):
            data.append({
                "video_id": video_id,
                "video_title": video_title,
                "status": "pending",
                "account1_comment_id": "",
                "account1_comment_text": "",
                "posted_at": "",
            })
            _write(S2_FILE, data)
            print(f"[S2] Added target: {video_id} — {video_title[:50]}")


def s2_get_pending() -> dict | None:
    lock = _Lock(S2_FILE + ".lock")
    with lock:
        for t in _read(S2_FILE):
            if t["status"] == "pending":
                return t
    return None


def s2_get_ready_for_reply(skip_delays: bool = False) -> dict | None:
    lock = _Lock(S2_FILE + ".lock")
    with lock:
        now = datetime.utcnow()
        for t in _read(S2_FILE):
            if t["status"] != "a_done":
                continue
            if skip_delays:
                return t
            posted = t.get("posted_at", "")
            if not posted:
                return t
            try:
                elapsed = now - datetime.fromisoformat(posted)
                if elapsed >= timedelta(hours=2):
                    return t
            except Exception:
                return t
    return None


def s2_update(video_id: str, **kwargs):
    lock = _Lock(S2_FILE + ".lock")
    with lock:
        data = _read(S2_FILE)
        for t in data:
            if t["video_id"] == video_id:
                t.update(kwargs)
                break
        _write(S2_FILE, data)


def s2_get_all_ids() -> set:
    lock = _Lock(S2_FILE + ".lock")
    with lock:
        return {t["video_id"] for t in _read(S2_FILE)}


# ── Strategy 3 ────────────────────────────────────────────────────────────────

def s3_get_available_topic_pair() -> str | None:
    lock = _Lock(PAIRS_FILE + ".lock")
    with lock:
        used = _read(PAIRS_FILE)
        now = datetime.utcnow()
        recent = set()
        for u in used:
            try:
                if (now - datetime.fromisoformat(u["used_at"])).days < 7:
                    recent.add(u["topic_pair"])
            except Exception:
                pass
    for pair in TOPIC_PAIRS_S3:
        if pair not in recent:
            return pair
    return None


def s3_mark_pair_used(topic_pair: str):
    lock = _Lock(PAIRS_FILE + ".lock")
    with lock:
        used = _read(PAIRS_FILE)
        used.append({"topic_pair": topic_pair, "used_at": datetime.utcnow().isoformat()})
        _write(PAIRS_FILE, used)


def s3_add_target(video_id: str, video_title: str, topic_pair: str):
    lock = _Lock(S3_FILE + ".lock")
    with lock:
        data = _read(S3_FILE)
        if not any(t["video_id"] == video_id for t in data):
            data.append({
                "video_id": video_id,
                "video_title": video_title,
                "topic_pair": topic_pair,
                "status": "pending",
                "account1_comment_id": "",
                "account1_comment_text": "",
                "a_posted_at": "",
            })
            _write(S3_FILE, data)
            print(f"[S3] Added target: {video_id} — {video_title[:50]} | {topic_pair}")


def s3_get_pending() -> dict | None:
    lock = _Lock(S3_FILE + ".lock")
    with lock:
        for t in _read(S3_FILE):
            if t["status"] == "pending":
                return t
    return None


def s3_get_a_done_ready(skip_delays: bool = False) -> dict | None:
    lock = _Lock(S3_FILE + ".lock")
    with lock:
        now = datetime.utcnow()
        for t in _read(S3_FILE):
            if t["status"] != "a_done":
                continue
            if skip_delays:
                return t
            posted = t.get("a_posted_at", "")
            if not posted:
                return t
            try:
                elapsed_min = (now - datetime.fromisoformat(posted)).total_seconds() / 60
                if elapsed_min >= 30:
                    return t
            except Exception:
                return t
    return None


def s3_update(video_id: str, **kwargs):
    lock = _Lock(S3_FILE + ".lock")
    with lock:
        data = _read(S3_FILE)
        for t in data:
            if t["video_id"] == video_id:
                t.update(kwargs)
                break
        _write(S3_FILE, data)


def s3_get_all_ids() -> set:
    lock = _Lock(S3_FILE + ".lock")
    with lock:
        return {t["video_id"] for t in _read(S3_FILE)}
