"""
Strategy 2 Scheduler — runs 4 full cycles per hour between 08:00 and 17:00.
Each cycle = Account1 → Account2 = 2 comments.
4 cycles/hour × 2 comments = 8 comments/hour.

Cycle budget: 14 min | Between-cycle pause: 20–60s | WATCH_MAX: 6 min
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
    "WATCH_MAX": "360",  # cap watch time at 6 min per session (2×6=12 min, leaves 2 min for navigation/posting)
})

PROFILE1 = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")
PROFILE2 = os.getenv("PROFILE_ACCOUNT2", "profiles/account2")

ACTIVE_START = 8   # 08:00
ACTIVE_END   = 17  # 17:00 — no runs at or after this hour

CYCLE_BUDGET = 840  # 14 minutes per cycle — 4 cycles/hour with up to 1 min between cycles


def _is_active_hour() -> bool:
    return ACTIVE_START <= datetime.now().hour < ACTIVE_END


def _wait_until_active():
    while not _is_active_hour():
        now = datetime.now()
        print(f"[S2-SCHED] Outside active hours ({now.strftime('%H:%M')}) — sleeping 5 min...")
        time.sleep(300)


BEHAVIORS = ["quick_commenter", "normal_watcher", "engaged_watcher", "skeptical_browser"]


def run_account(module: str, profile: str, label: str, behavior: str = "") -> bool:
    print(f"\n{'=' * 60}")
    print(f"[S2-SCHED] {label}")
    print(f"{'=' * 60}")
    env = {**os.environ, "PROFILE_PATH": profile}
    if behavior:
        env["WATCH_BEHAVIOR"] = behavior
    result = subprocess.run(
        [sys.executable, "-c", f"from {module} import run_session; run_session()"],
        env=env,
    )
    if result.returncode != 0:
        print(f"[S2-SCHED] WARNING: {module} exited with code {result.returncode}")
    return result.returncode == 0


def run_cycle(cycle_num: int):
    cycle_start = time.monotonic()
    print(f"\n[S2-SCHED] ===== Cycle #{cycle_num} starting at {datetime.now().strftime('%H:%M:%S')} =====")

    behaviors = random.sample(BEHAVIORS, 2)

    if not run_account("s2_account1", PROFILE1, "Account 1 — Observation", behaviors[0]):
        print("[S2-SCHED] Account 1 failed — skipping rest of cycle")
        return

    pause = random.uniform(20, 120)
    print(f"\n[S2-SCHED] Pausing {pause:.0f}s before Account 2...")
    time.sleep(pause)

    run_account("s2_account2", PROFILE2, "Account 2 — Deep Dive", behaviors[1])

    elapsed = time.monotonic() - cycle_start
    print(f"\n[S2-SCHED] Cycle #{cycle_num} complete at {datetime.now().strftime('%H:%M:%S')} ({elapsed:.0f}s elapsed)")


def main():
    print(f"[S2-SCHED] Scheduler started — active window: {ACTIVE_START:02d}:00 – {ACTIVE_END:02d}:00")
    cycle_num = 0

    while True:
        _wait_until_active()

        cycle_num += 1
        run_cycle(cycle_num)

        if _is_active_hour():
            between = random.uniform(20, 60)
            print(f"\n[S2-SCHED] Waiting {between:.0f}s before next cycle...")
            time.sleep(between)


if __name__ == "__main__":
    main()
