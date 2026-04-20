"""
End-to-end test for Strategy 2 (Depth Escalation).
Runs Account 1 → Account 2 in sequence (2-hour wait bypassed).
DRY_RUN=False | SKIP_DELAYS=True | WATCH_MAX=30
"""
import os
import sys
import time
import subprocess
from dotenv import load_dotenv

load_dotenv()

os.environ.update({
    "DRY_RUN": "False",
    "SKIP_DELAYS": "True",
    "WATCH_MAX": "30",
})

PROFILE1 = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")
PROFILE2 = os.getenv("PROFILE_ACCOUNT2", "profiles/account2")


def run_account(module: str, profile: str, label: str) -> bool:
    print(f"\n{'=' * 60}")
    print(f"[TEST-S2] {label}")
    print(f"{'=' * 60}")
    env = {**os.environ, "PROFILE_PATH": profile}
    result = subprocess.run(
        [sys.executable, "-c", f"from {module} import run_session; run_session()"],
        env=env,
    )
    if result.returncode != 0:
        print(f"[TEST-S2] WARNING: exited with code {result.returncode}")
    return result.returncode == 0


def main():
    print("[TEST-S2] Strategy 2 end-to-end test")
    print(f"  Profiles: {PROFILE1}  {PROFILE2}\n")

    if not run_account("s2_account1", PROFILE1, "Account 1 — Observation"):
        print("[TEST-S2] Account 1 failed — aborting"); return

    print("\n[TEST-S2] Pausing 20s for YouTube to register comment...")
    time.sleep(20)

    run_account("s2_account2", PROFILE2, "Account 2 — Deep Dive")

    print("\n[TEST-S2] Done.")


if __name__ == "__main__":
    main()
