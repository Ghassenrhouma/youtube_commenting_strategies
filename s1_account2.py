"""Strategy 1, Account 2 — Challenger: replies to Account 1 with counter-experience + DocShipper."""
import os
import time
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
os.environ["PROFILE_PATH"] = os.getenv("PROFILE_ACCOUNT2", "profiles/account2")

DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SKIP_DELAYS = os.getenv("SKIP_DELAYS", "False").lower() == "true"
ACCOUNT_ID = "account2"
STRATEGY = "s1"

from comment_generator import generate_s1_challenger
from comment_poster import post_reply
from coordination import sleep_if_night, s1_get_a_done_ready, s1_update
from tracker import log_action


def run_session():
    target = s1_get_a_done_ready(skip_delays=SKIP_DELAYS)

    if not target:
        print("[S1-A2] No ready targets (waiting for 20+ min after account1 post)")
        return

    video_id = target["video_id"]
    video_title = target["video_title"]
    account1_comment = target["account1_comment_text"]
    account1_comment_id = target["account1_comment_id"]
    print(f"[S1-A2] Processing: {video_id} — {video_title[:60]}")

    reply = generate_s1_challenger(video_title, account1_comment)
    print(f"[S1-A2] Generated reply: {reply[:100]}")

    reply_id = post_reply(
        video_id=video_id,
        parent_comment_id=account1_comment_id,
        reply_text=reply,
        comment_text=account1_comment,
    )
    print(f"[S1-A2] Posted — reply_id: {reply_id}")

    s1_update(
        video_id,
        status="b_done",
        account2_comment_id=reply_id,
        account2_comment_text=reply,
        b_posted_at=datetime.utcnow().isoformat(),
    )

    log_action(
        strategy=STRATEGY,
        account=ACCOUNT_ID,
        video_id=video_id,
        video_title=video_title,
        role="challenger",
        replied_to_comment=account1_comment,
        text=reply,
        comment_id=reply_id,
        status="posted",
        dry_run=DRY_RUN,
    )
    print(f"[S1-A2] Done — status set to b_done")


def main():
    print(f"[S1-A2] Starting — DRY_RUN={DRY_RUN}, SKIP_DELAYS={SKIP_DELAYS}")
    while True:
        sleep_if_night()
        try:
            run_session()
        except Exception as e:
            print(f"[S1-A2] ERROR: {e}")
        gap = random.uniform(600, 1200) if not SKIP_DELAYS else 10
        print(f"[S1-A2] Sleeping {gap:.0f}s before next check")
        time.sleep(gap)


if __name__ == "__main__":
    main()
