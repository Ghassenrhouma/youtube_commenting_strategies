"""Strategy 1, Account 1 — Initiator: posts top-level comment with DocShipper mention."""
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
STRATEGY = "s1"

from comment_generator import generate_s1_initiator
from comment_poster import post_comment
from coordination import (
    sleep_if_night,
    s1_add_target, s1_get_pending, s1_update, s1_get_all_ids,
)
from tracker import log_action
from video_finder import get_videos_by_keyword, get_channel_recent_videos, SEARCH_QUERIES, TARGET_CHANNELS


def _find_new_videos(seen_ids: set, max_results: int = 3) -> list:
    if random.random() < 0.5:
        channel = random.choice(TARGET_CHANNELS)
        print(f"[S1-A1] Channel browse: '{channel['name']}'")
        videos = get_channel_recent_videos(channel["url"], channel["name"], max_results=12)
    else:
        query = random.choice(SEARCH_QUERIES)
        print(f"[S1-A1] Searching: '{query}'")
        videos = get_videos_by_keyword(query, max_results=12)
    return [v for v in videos if v["video_id"] not in seen_ids][:max_results]


def run_session():
    target = s1_get_pending()

    if not target:
        seen_ids = s1_get_all_ids()
        new_videos = _find_new_videos(seen_ids)
        for v in new_videos:
            s1_add_target(v["video_id"], v["video_title"])
        target = s1_get_pending()

    if not target:
        print("[S1-A1] No pending targets found — will retry")
        return

    video_id = target["video_id"]
    video_title = target["video_title"]
    print(f"[S1-A1] Processing: {video_id} — {video_title[:60]}")

    comment = generate_s1_initiator(video_title, "")
    print(f"[S1-A1] Generated comment: {comment[:100]}")

    comment_id = post_comment(video_id, comment, video_title=video_title)
    print(f"[S1-A1] Posted — comment_id: {comment_id}")

    s1_update(
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
        role="initiator",
        replied_to_comment="",
        text=comment,
        comment_id=comment_id,
        status="posted",
        dry_run=DRY_RUN,
    )
    print(f"[S1-A1] Done — status set to a_done")


def main():
    print(f"[S1-A1] Starting — DRY_RUN={DRY_RUN}, SKIP_DELAYS={SKIP_DELAYS}")
    while True:
        sleep_if_night()
        try:
            run_session()
        except Exception as e:
            print(f"[S1-A1] ERROR: {e}")
        gap = random.uniform(2700, 5400) if not SKIP_DELAYS else 10
        print(f"[S1-A1] Sleeping {gap:.0f}s before next session")
        time.sleep(gap)


if __name__ == "__main__":
    main()
