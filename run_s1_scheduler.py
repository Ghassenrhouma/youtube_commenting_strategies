"""
Strategy 1 Scheduler — runs 3 full cycles per hour between 08:00 and 17:00.
Each cycle = Account1 → Account2 → Account3 = 3 comments.
3 cycles/hour × 3 comments = 9 comments/hour.

Cycle budget: 18 min | Between-cycle pause: 20–120s | WATCH_MAX: 5 min
"""
import os
import sys
import time
import random
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

os.environ.update({
    "DRY_RUN": "False",
    "SKIP_DELAYS": "True",
    "WATCH_MAX": "5",  # cap watch time at 5 min per session (3×5=15 min, leaves 3 min for navigation/posting)
})

PROFILE1 = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")
PROFILE2 = os.getenv("PROFILE_ACCOUNT2", "profiles/account2")
PROFILE3 = os.getenv("PROFILE_ACCOUNT3", "profiles/account3")

ACTIVE_START = 8 # 08:00
ACTIVE_END   = 19  # 17:00 (5 PM) — no runs at or after this hour


def _is_active_hour() -> bool:
    return ACTIVE_START <= datetime.now().hour < ACTIVE_END

def _wait_until_active():
    """Block until we are inside the active window."""
    while not _is_active_hour():
        now = datetime.now()
        print(f"[SCHEDULER] Outside active hours ({now.strftime('%H:%M')}) — sleeping 5 min...")
        time.sleep(300)


def _seconds_until_next_slot() -> float:
    """Return seconds until the next :00 or :30 mark."""
    now = datetime.now()
    minutes = now.minute
    seconds = now.second
    if minutes < 30:
        remaining = (30 - minutes) * 60 - seconds
    else:
        remaining = (60 - minutes) * 60 - seconds
    return max(0.0, remaining)


CYCLE_BUDGET = 1080  # 18 minutes per cycle — 3 cycles/hour with up to 2 min between cycles


BEHAVIORS = ["quick_commenter", "normal_watcher", "engaged_watcher", "skeptical_browser"]


def run_account(module: str, profile: str, label: str, behavior: str = "") -> bool:
    print(f"\n{'=' * 60}")
    print(f"[S1-SCHED] {label}")
    print(f"{'=' * 60}")
    env = {**os.environ, "PROFILE_PATH": profile}
    if behavior:
        env["WATCH_BEHAVIOR"] = behavior
    result = subprocess.run(
        [sys.executable, "-c", f"from {module} import run_session; run_session()"],
        env=env,
    )
    if result.returncode != 0:
        print(f"[S1-SCHED] WARNING: {module} exited with code {result.returncode}")
    return result.returncode == 0


def run_cycle(cycle_num: int):
    cycle_start = time.monotonic()
    print(f"\n[S1-SCHED] ===== Cycle #{cycle_num} starting at {datetime.now().strftime('%H:%M:%S')} =====")

    behaviors = random.sample(BEHAVIORS, 3)

    if not run_account("s1_account1", PROFILE1, "Account 1 — Initiator", behaviors[0]):
        print("[S1-SCHED] Account 1 failed — skipping rest of cycle")
        return

    pause = random.uniform(20, 120)
    print(f"\n[S1-SCHED] Pausing {pause:.0f}s before Account 2...")
    time.sleep(pause)

    if not run_account("s1_account2", PROFILE2, "Account 2 — Challenger", behaviors[1]):
        print("[S1-SCHED] Account 2 failed — skipping account 3")
        return

    pause = random.uniform(20, 120)
    print(f"\n[S1-SCHED] Pausing {pause:.0f}s before Account 3...")
    time.sleep(pause)

    run_account("s1_account3", PROFILE3, "Account 3 — Synthesizer", behaviors[2])

    elapsed = time.monotonic() - cycle_start
    print(f"\n[S1-SCHED] Cycle #{cycle_num} complete at {datetime.now().strftime('%H:%M:%S')} ({elapsed:.0f}s elapsed)")


def main():
    print(f"[S1-SCHED] Scheduler started — active window: {ACTIVE_START:02d}:00 – {ACTIVE_END:02d}:00")
    cycle_num = 0

    while True:
        _wait_until_active()

        cycle_num += 1
        run_cycle(cycle_num)

        if _is_active_hour():
            between = random.uniform(20, 120)
            print(f"\n[S1-SCHED] Waiting {between:.0f}s before next cycle...")
            time.sleep(between)


if __name__ == "__main__":
    main()
