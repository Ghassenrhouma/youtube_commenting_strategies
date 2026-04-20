"""Strategy 3, Account 2 — Position B: counter-argument reply 30+ min later, no DocShipper."""
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()
os.environ["PROFILE_PATH"] = os.getenv("PROFILE_ACCOUNT2", "profiles/account2")

DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SKIP_DELAYS = os.getenv("SKIP_DELAYS", "False").lower() == "true"
ACCOUNT_ID = "account2"
STRATEGY = "s3"

from comment_generator import generate_s3_position_b
from comment_poster import post_reply
from coordination import sleep_if_night, s3_get_a_done_ready, s3_update
from tracker import log_action


def run_session():
    target = s3_get_a_done_ready(skip_delays=SKIP_DELAYS)

    if not target:
        print("[S3-A2] No ready targets (waiting for 30+ min after account1 post)")
        return

    video_id = target["video_id"]
    video_title = target["video_title"]
    topic_pair = target["topic_pair"]
    account1_comment = target["account1_comment_text"]
    account1_comment_id = target["account1_comment_id"]
    print(f"[S3-A2] Processing: {video_id} — {video_title[:60]} | topic: {topic_pair}")

    reply = generate_s3_position_b(video_title, topic_pair, account1_comment)
    print(f"[S3-A2] Generated reply: {reply[:100]}")

    reply_id = post_reply(
        video_id=video_id,
        parent_comment_id=account1_comment_id,
        reply_text=reply,
        comment_text=account1_comment,
    )
    print(f"[S3-A2] Posted — reply_id: {reply_id}")

    s3_update(video_id, status="complete")

    log_action(
        strategy=STRATEGY,
        account=ACCOUNT_ID,
        video_id=video_id,
        video_title=video_title,
        role="position_b",
        replied_to_comment=account1_comment,
        text=reply,
        comment_id=reply_id,
        status="posted",
        dry_run=DRY_RUN,
    )
    print(f"[S3-A2] Done — status set to complete")


def main():
    print(f"[S3-A2] Starting — DRY_RUN={DRY_RUN}, SKIP_DELAYS={SKIP_DELAYS}")
    while True:
        sleep_if_night()
        try:
            run_session()
        except Exception as e:
            print(f"[S3-A2] ERROR: {e}")
        gap = random.uniform(900, 1800) if not SKIP_DELAYS else 10
        print(f"[S3-A2] Sleeping {gap:.0f}s before next check")
        time.sleep(gap)


if __name__ == "__main__":
    main()
