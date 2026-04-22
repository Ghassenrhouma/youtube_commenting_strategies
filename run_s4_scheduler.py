"""
Strategy 4 Scheduler — runs 4 cycles per hour between 08:00 and 17:00.
Each cycle = Account1 scrapes a video and replies to a replyable comment.
4 cycles/hour × 1 comment = 4 comments/hour.

Cycle budget: 14 min | WATCH_MAX: 6 min | Between-cycle pause: 20–60s
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
    "SKIP_DELAYS": "False",
    "WATCH_MAX": "360",  # 6 min per session
})

PROFILE1 = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")

ACTIVE_START = 8
ACTIVE_END   = 17

CYCLE_BUDGET = 840  # 14 minutes per cycle — 4 cycles/hour with up to 1 min between cycles


def _is_active_hour() -> bool:
    return ACTIVE_START <= datetime.now().hour < ACTIVE_END


def _wait_until_active():
    while not _is_active_hour():
        print(f"[S4-SCHED] Outside active hours ({datetime.now().strftime('%H:%M')}) — sleeping 5 min...")
        time.sleep(300)


def run_cycle(cycle_num: int):
    cycle_start = time.monotonic()
    print(f"\n[S4-SCHED] ===== Cycle #{cycle_num} starting at {datetime.now().strftime('%H:%M:%S')} =====")

    env = {**os.environ, "PROFILE_PATH": PROFILE1}
    result = subprocess.run(
        [sys.executable, "-c", "from s4_account1 import run_session; from tracker import get_seen_video_ids; run_session(get_seen_video_ids())"],
        env=env,
    )
    if result.returncode != 0:
        print(f"[S4-SCHED] WARNING: s4_account1 exited with code {result.returncode}")

    elapsed = time.monotonic() - cycle_start
    print(f"\n[S4-SCHED] Cycle #{cycle_num} complete at {datetime.now().strftime('%H:%M:%S')} ({elapsed:.0f}s elapsed)")


def main():
    print(f"[S4-SCHED] Scheduler started — active window: {ACTIVE_START:02d}:00 – {ACTIVE_END:02d}:00")
    cycle_num = 0

    while True:
        _wait_until_active()

        cycle_num += 1
        run_cycle(cycle_num)

        if _is_active_hour():
            between = random.uniform(20, 60)
            print(f"\n[S4-SCHED] Waiting {between:.0f}s before next cycle...")
            time.sleep(between)


if __name__ == "__main__":
    main()
