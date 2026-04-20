"""Strategy 4, Account 1 — Replyable Comments: scans videos, replies to questions/problems + DocShipper."""
import os
import re
import time
import random
from dotenv import load_dotenv

load_dotenv()
os.environ["PROFILE_PATH"] = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")

DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SKIP_DELAYS = os.getenv("SKIP_DELAYS", "False").lower() == "true"
ACCOUNT_ID = "account1"
STRATEGY = "s4"

from comment_generator import generate_s4_reply
from comment_poster import scrape_and_reply
from coordination import sleep_if_night
from tracker import log_action, get_seen_video_ids
from video_finder import get_popular_videos_for_replies


_REPLYABLE = re.compile(
    r"\bhow (do|can|should|to)\b|"
    r"\bwhat (is|are|should|does)\b|"
    r"\bwhy (is|are|does|would)\b|"
    r"\bcan (someone|anyone|you)\b|"
    r"\bdoes anyone\b|"
    r"\bhelp (me|with|on)\b|"
    r"\bi need (help|advice|guidance)\b|"
    r"i don'?t (understand|know|get)\b|"
    r"\bconfused (about|by|with)\b|"
    r"\bi('ve| have) (had|been having)\b.{0,30}\b(issue|problem|trouble)\b|"
    r"\bhaving (trouble|issues?|difficulty|problems?)\b|"
    r"\bnot working\b|"
    r"\bfailed to\b|"
    r"\bcouldn'?t\b",
    re.IGNORECASE,
)

_PROMO = re.compile(
    r"check (out|this)|link in (bio|desc)|free trial|sign up|dm me|visit my",
    re.IGNORECASE,
)


def is_replyable_s4(text: str) -> bool:
    if len(text.split()) < 15:
        return False
    if not _REPLYABLE.search(text):
        return False
    if _PROMO.search(text):
        return False
    return True


def run_session(seen_ids: set):
    print(f"[S4-A1] Finding candidate videos ({len(seen_ids)} already seen)")
    candidates = get_popular_videos_for_replies(max_results=5, seen_ids=seen_ids)

    if not candidates:
        print("[S4-A1] No candidate videos found")
        return

    random.shuffle(candidates)
    video = candidates[0]
    video_id = video["video_id"]
    video_title = video["title"]

    if video_id in seen_ids:
        print(f"[S4-A1] Skipping already-seen video: {video_id}")
        return

    print(f"[S4-A1] Targeting: {video_id} — {video_title[:60]}")

    if DRY_RUN:
        print(f"[DRY RUN] Would scan and reply on {video_id}: '{video_title}'")
        seen_ids.add(video_id)
        log_action(
            strategy=STRATEGY,
            account=ACCOUNT_ID,
            video_id=video_id,
            video_title=video_title,
            role="replyable",
            replied_to_comment="(dry run)",
            text="(dry run)",
            comment_id="dry_run_id",
            status="dry_run",
            dry_run=True,
        )
        return

    result = scrape_and_reply(
        video_id=video_id,
        video_title=video_title,
        is_replyable_fn=is_replyable_s4,
        generate_reply_fn=generate_s4_reply,
    )
    seen_ids.add(video_id)
    print(f"[S4-A1] Reply posted — comment_id: {result['comment_id']}")

    log_action(
        strategy=STRATEGY,
        account=ACCOUNT_ID,
        video_id=video_id,
        video_title=video_title,
        role="replyable",
        replied_to_comment=result["comment_text"],
        text=result["reply_text"],
        comment_id=result["comment_id"],
        status="posted",
        dry_run=False,
    )
    print(f"[S4-A1] Done — logged to tracker")


def main():
    print(f"[S4-A1] Starting — DRY_RUN={DRY_RUN}, SKIP_DELAYS={SKIP_DELAYS}")
    seen_ids = get_seen_video_ids(account=ACCOUNT_ID)

    while True:
        sleep_if_night()
        try:
            run_session(seen_ids)
        except Exception as e:
            print(f"[S4-A1] ERROR: {e}")
        gap = random.uniform(2700, 5400) if not SKIP_DELAYS else 10
        print(f"[S4-A1] Sleeping {gap:.0f}s before next session")
        time.sleep(gap)


if __name__ == "__main__":
    main()
