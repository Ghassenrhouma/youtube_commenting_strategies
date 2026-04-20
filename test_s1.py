"""
End-to-end test for Strategy 1 (Thread Building).
Runs Account 1 → Account 2 → Account 3 in sequence.
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
PROFILE3 = os.getenv("PROFILE_ACCOUNT3", "profiles/account3")


def run_account(module: str, profile: str, label: str) -> bool:
    print(f"\n{'=' * 60}")
    print(f"[TEST-S1] {label}")
    print(f"{'=' * 60}")
    env = {**os.environ, "PROFILE_PATH": profile}
    result = subprocess.run(
        [sys.executable, "-c", f"from {module} import run_session; run_session()"],
        env=env,
    )
    if result.returncode != 0:
        print(f"[TEST-S1] WARNING: exited with code {result.returncode}")
    return result.returncode == 0


def main():
    print("[TEST-S1] Strategy 1 end-to-end test")
    print(f"  Profiles: {PROFILE1}  {PROFILE2}  {PROFILE3}\n")

    if not run_account("s1_account1", PROFILE1, "Account 1 — Initiator"):
        print("[TEST-S1] Account 1 failed — aborting"); return

    print("\n[TEST-S1] Pausing 20s for YouTube to register comment...")
    time.sleep(20)

    if not run_account("s1_account2", PROFILE2, "Account 2 — Challenger"):
        print("[TEST-S1] Account 2 failed — aborting"); return

    print("\n[TEST-S1] Pausing 20s for YouTube to register reply...")
    time.sleep(20)

    run_account("s1_account3", PROFILE3, "Account 3 — Synthesizer")

    print("\n[TEST-S1] Done.")


if __name__ == "__main__":
    main()
