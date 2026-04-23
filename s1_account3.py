"""Strategy 1, Account 3 — Synthesizer: ties both threads together, no DocShipper mention."""
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("PROFILE_PATH", "/app/profiles/account3")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SKIP_DELAYS = os.getenv("SKIP_DELAYS", "False").lower() == "true"
ACCOUNT_ID = "account3"
STRATEGY = "s1"

from comment_generator import generate_s1_synthesizer
from comment_poster import post_reply
from coordination import sleep_if_night, s1_get_b_done_ready, s1_update
from tracker import log_action


def run_session():
    target = s1_get_b_done_ready(skip_delays=SKIP_DELAYS)

    if not target:
        print("[S1-A3] No ready targets (waiting for 20+ min after account2 post)")
        return

    video_id = target["video_id"]
    video_title = target["video_title"]
    account1_comment = target["account1_comment_text"]
    account2_comment = target["account2_comment_text"]
    account2_comment_id = target["account2_comment_id"]
    print(f"[S1-A3] Processing: {video_id} — {video_title[:60]}")

    reply = generate_s1_synthesizer(video_title, account1_comment, account2_comment)
    print(f"[S1-A3] Generated reply: {reply[:100]}")

    reply_id = post_reply(
        video_id=video_id,
        parent_comment_id=account2_comment_id,
        reply_text=reply,
        comment_text=account2_comment,
        top_level_comment_text=account1_comment,
    )
    print(f"[S1-A3] Posted — reply_id: {reply_id}")

    s1_update(
        video_id,
        status="complete",
        account3_comment_id=reply_id,
    )

    log_action(
        strategy=STRATEGY,
        account=ACCOUNT_ID,
        video_id=video_id,
        video_title=video_title,
        role="synthesizer",
        replied_to_comment=account2_comment,
        text=reply,
        comment_id=reply_id,
        status="posted",
        dry_run=DRY_RUN,
    )
    print(f"[S1-A3] Done — status set to complete")


def main():
    print(f"[S1-A3] Starting — DRY_RUN={DRY_RUN}, SKIP_DELAYS={SKIP_DELAYS}")
    while True:
        sleep_if_night()
        try:
            run_session()
        except Exception as e:
            print(f"[S1-A3] ERROR: {e}")
        gap = random.uniform(600, 1200) if not SKIP_DELAYS else 10
        print(f"[S1-A3] Sleeping {gap:.0f}s before next check")
        time.sleep(gap)


if __name__ == "__main__":
    main()
