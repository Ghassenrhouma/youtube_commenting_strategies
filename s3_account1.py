"""Strategy 3, Account 1 — Position A: top-level comment defending one side + DocShipper."""
import os
import time
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("PROFILE_PATH", "/app/profiles/account1")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SKIP_DELAYS = os.getenv("SKIP_DELAYS", "False").lower() == "true"
ACCOUNT_ID = "account1"
STRATEGY = "s3"

from comment_generator import generate_s3_position_a
from comment_poster import post_comment
from coordination import (
    sleep_if_night,
    s3_add_target, s3_get_pending, s3_update, s3_get_all_ids,
    s3_get_available_topic_pair, s3_mark_pair_used,
)
from tracker import log_action
from video_finder import get_videos_by_keyword, get_channel_recent_videos, SEARCH_QUERIES, TARGET_CHANNELS


def _find_new_videos(seen_ids: set, max_results: int = 3) -> list:
    if random.random() < 0.5:
        channel = random.choice(TARGET_CHANNELS)
        print(f"[S3-A1] Channel browse: '{channel['name']}'")
        videos = get_channel_recent_videos(channel["url"], channel["name"], max_results=12)
    else:
        query = random.choice(SEARCH_QUERIES)
        print(f"[S3-A1] Searching: '{query}'")
        videos = get_videos_by_keyword(query, max_results=12)
    return [v for v in videos if v["video_id"] not in seen_ids][:max_results]


def run_session():
    target = s3_get_pending()

    if not target:
        topic_pair = s3_get_available_topic_pair()
        if not topic_pair:
            print("[S3-A1] All topic pairs used within the past 7 days — will retry later")
            return

        seen_ids = s3_get_all_ids()
        new_videos = _find_new_videos(seen_ids)
        for v in new_videos:
            s3_add_target(v["video_id"], v["video_title"], topic_pair)
        s3_mark_pair_used(topic_pair)
        target = s3_get_pending()

    if not target:
        print("[S3-A1] No pending targets found — will retry")
        return

    video_id = target["video_id"]
    video_title = target["video_title"]
    topic_pair = target["topic_pair"]
    print(f"[S3-A1] Processing: {video_id} — {video_title[:60]} | topic: {topic_pair}")

    comment = generate_s3_position_a(video_title, topic_pair)
    print(f"[S3-A1] Generated comment: {comment[:100]}")

    comment_id = post_comment(video_id, comment, video_title=video_title)
    print(f"[S3-A1] Posted — comment_id: {comment_id}")

    s3_update(
        video_id,
        status="a_done",
        account1_comment_id=comment_id,
        account1_comment_text=comment,
        a_posted_at=datetime.utcnow().isoformat(),
    )

    log_action(
        strategy=STRATEGY,
        account=ACCOUNT_ID,
        video_id=video_id,
        video_title=video_title,
        role="position_a",
        replied_to_comment="",
        text=comment,
        comment_id=comment_id,
        status="posted",
        dry_run=DRY_RUN,
    )
    print(f"[S3-A1] Done — status set to a_done")


def main():
    print(f"[S3-A1] Starting — DRY_RUN={DRY_RUN}, SKIP_DELAYS={SKIP_DELAYS}")
    while True:
        sleep_if_night()
        try:
            run_session()
        except Exception as e:
            print(f"[S3-A1] ERROR: {e}")
        gap = random.uniform(2700, 5400) if not SKIP_DELAYS else 10
        print(f"[S3-A1] Sleeping {gap:.0f}s before next session")
        time.sleep(gap)


if __name__ == "__main__":
    main()
