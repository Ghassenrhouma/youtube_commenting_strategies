"""
End-to-end test for Strategy 4 (Replyable Comments).
Finds a video, scans comments, posts one reply.
DRY_RUN=False | SKIP_DELAYS=True | WATCH_MAX=30
"""
import os
import sys
import subprocess
from dotenv import load_dotenv

load_dotenv()

os.environ.update({
    "DRY_RUN": "False",
    "SKIP_DELAYS": "True",
    "WATCH_MAX": "30",
})

PROFILE1 = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")


def main():
    print("[TEST-S4] Strategy 4 end-to-end test")
    print(f"  Profile: {PROFILE1}\n")
    print(f"{'=' * 60}")
    print(f"[TEST-S4] Account 1 — Replyable Comments")
    print(f"{'=' * 60}")

    env = {**os.environ, "PROFILE_PATH": PROFILE1}
    result = subprocess.run(
        [sys.executable, "-c", "from s4_account1 import run_session; seen = set(); run_session(seen)"],
        env=env,
    )
    if result.returncode != 0:
        print(f"[TEST-S4] WARNING: exited with code {result.returncode}")

    print("\n[TEST-S4] Done.")


if __name__ == "__main__":
    main()
