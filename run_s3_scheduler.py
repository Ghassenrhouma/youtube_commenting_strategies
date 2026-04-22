"""
Strategy 3 Scheduler — runs 3 cycles per hour between 08:00 and 17:00.
Each cycle = random depth: 2, 3, or 4 comments (back-and-forth debate).
  depth 2: A1 Position A  →  A2 Position B
  depth 3: A1 → A2 → A1 counter
  depth 4: A1 → A2 → A1 counter → A2 final word

Cycle budget: 18 min | WATCH_MAX: 3 min | Between-cycle pause: 20–120s
"""
import os
import sys
import time
import random
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

os.environ.update({
    "DRY_RUN": "False",
    "SKIP_DELAYS": "True",
    "WATCH_MAX": "180",  # 3 min per session — up to 4 sessions × 3 min = 12 min
})

PROFILE1 = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")
PROFILE2 = os.getenv("PROFILE_ACCOUNT2", "profiles/account2")

ACTIVE_START = 8
ACTIVE_END   = 17

CYCLE_BUDGET = 1080  # 18 minutes


# ── Imports (after env is set) ────────────────────────────────────────────────

from comment_generator import (
    generate_s3_position_a,
    generate_s3_position_b,
    generate_s3_counter_a,
    generate_s3_counter_b,
)
from comment_poster import post_comment, post_reply
from coordination import (
    s3_add_target, s3_get_pending, s3_update, s3_get_all_ids,
    s3_get_available_topic_pair, s3_mark_pair_used,
)
from tracker import log_action
from video_finder import get_videos_by_keyword, get_channel_recent_videos, SEARCH_QUERIES, TARGET_CHANNELS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_active_hour() -> bool:
    return ACTIVE_START <= datetime.now().hour < ACTIVE_END


def _wait_until_active():
    while not _is_active_hour():
        print(f"[S3-SCHED] Outside active hours ({datetime.now().strftime('%H:%M')}) — sleeping 5 min...")
        time.sleep(300)


def _find_new_videos(seen_ids: set, max_results: int = 3) -> list:
    if random.random() < 0.5:
        channel = random.choice(TARGET_CHANNELS)
        print(f"[S3-SCHED] Channel browse: '{channel['name']}'")
        videos = get_channel_recent_videos(channel["url"], channel["name"], max_results=12)
    else:
        query = random.choice(SEARCH_QUERIES)
        print(f"[S3-SCHED] Searching: '{query}'")
        videos = get_videos_by_keyword(query, max_results=12)
    return [v for v in videos if v["video_id"] not in seen_ids][:max_results]


def _pause(label: str, low: float, high: float, remaining: float):
    secs = min(random.uniform(low, high), remaining)
    print(f"\n[S3-SCHED] Pausing {secs:.0f}s {label}...")
    time.sleep(secs)


# ── Cycle ─────────────────────────────────────────────────────────────────────

def run_cycle(cycle_num: int, depth: int):
    cycle_start = time.monotonic()

    def remaining() -> float:
        return max(0.0, CYCLE_BUDGET - (time.monotonic() - cycle_start))

    print(f"\n[S3-SCHED] ===== Cycle #{cycle_num} | depth={depth} | {datetime.now().strftime('%H:%M:%S')} =====")

    # ── Video discovery ────────────────────────────────────────────────────────
    topic_pair = s3_get_available_topic_pair()
    if not topic_pair:
        print("[S3-SCHED] All topic pairs used this week — skipping cycle")
        return

    target = s3_get_pending()
    if not target:
        seen_ids = s3_get_all_ids()
        new_videos = _find_new_videos(seen_ids)
        if not new_videos:
            print("[S3-SCHED] No new videos found — skipping cycle")
            return
        for v in new_videos:
            s3_add_target(v["video_id"], v["video_title"], topic_pair)
        s3_mark_pair_used(topic_pair)
        target = s3_get_pending()

    if not target:
        print("[S3-SCHED] No pending target after discovery — skipping cycle")
        return

    video_id    = target["video_id"]
    video_title = target["video_title"]
    topic_pair  = target["topic_pair"]
    print(f"[S3-SCHED] Video: {video_id} — {video_title[:60]}")
    print(f"[S3-SCHED] Topic: {topic_pair}")

    # ── Round 1: Account 1 — Position A ───────────────────────────────────────
    os.environ["PROFILE_PATH"] = PROFILE1
    a1_text = generate_s3_position_a(video_title, topic_pair)
    print(f"[S3-SCHED] A1 comment: {a1_text[:100]}")

    a1_id = post_comment(video_id, a1_text, video_title=video_title)
    print(f"[S3-SCHED] A1 posted — id: {a1_id}")

    s3_update(video_id, status="a_done", account1_comment_id=a1_id,
              account1_comment_text=a1_text, a_posted_at=datetime.utcnow().isoformat())

    log_action(strategy="s3", account="account1", video_id=video_id, video_title=video_title,
               role="position_a", replied_to_comment="", text=a1_text,
               comment_id=a1_id, status="posted")

    if remaining() < 60:
        print("[S3-SCHED] Budget exhausted after Round 1 — stopping")
        return

    _pause("before Round 2", 20, 120, remaining())

    # ── Round 2: Account 2 — Position B ───────────────────────────────────────
    os.environ["PROFILE_PATH"] = PROFILE2
    a2_text = generate_s3_position_b(video_title, topic_pair, a1_text)
    print(f"[S3-SCHED] A2 reply: {a2_text[:100]}")

    a2_id = post_reply(video_id=video_id, parent_comment_id=a1_id,
                       reply_text=a2_text, comment_text=a1_text)
    print(f"[S3-SCHED] A2 posted — id: {a2_id}")

    s3_update(video_id, status="complete")

    log_action(strategy="s3", account="account2", video_id=video_id, video_title=video_title,
               role="position_b", replied_to_comment=a1_text, text=a2_text,
               comment_id=a2_id, status="posted")

    if depth < 3 or remaining() < 60:
        print(f"[S3-SCHED] Cycle #{cycle_num} done at depth 2")
        return

    _pause("before Round 3", 20, 120, remaining())

    # ── Round 3: Account 1 — Counter-reply ────────────────────────────────────
    os.environ["PROFILE_PATH"] = PROFILE1
    a1_counter = generate_s3_counter_a(video_title, topic_pair, a2_text)
    print(f"[S3-SCHED] A1 counter: {a1_counter[:100]}")

    a1_counter_id = post_reply(video_id=video_id, parent_comment_id=a1_id,
                               reply_text=a1_counter, comment_text=a2_text,
                               top_level_comment_text=a1_text)
    print(f"[S3-SCHED] A1 counter posted — id: {a1_counter_id}")

    log_action(strategy="s3", account="account1", video_id=video_id, video_title=video_title,
               role="counter_a", replied_to_comment=a2_text, text=a1_counter,
               comment_id=a1_counter_id, status="posted")

    if depth < 4 or remaining() < 60:
        print(f"[S3-SCHED] Cycle #{cycle_num} done at depth 3")
        return

    _pause("before Round 4", 20, 120, remaining())

    # ── Round 4: Account 2 — Final word ───────────────────────────────────────
    os.environ["PROFILE_PATH"] = PROFILE2
    a2_final = generate_s3_counter_b(video_title, topic_pair, a1_counter)
    print(f"[S3-SCHED] A2 final: {a2_final[:100]}")

    a2_final_id = post_reply(video_id=video_id, parent_comment_id=a1_id,
                             reply_text=a2_final, comment_text=a1_counter,
                             top_level_comment_text=a1_text)
    print(f"[S3-SCHED] A2 final posted — id: {a2_final_id}")

    log_action(strategy="s3", account="account2", video_id=video_id, video_title=video_title,
               role="counter_b", replied_to_comment=a1_counter, text=a2_final,
               comment_id=a2_final_id, status="posted")

    elapsed = time.monotonic() - cycle_start
    print(f"\n[S3-SCHED] Cycle #{cycle_num} complete at depth 4 — {elapsed:.0f}s elapsed")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[S3-SCHED] Scheduler started — active window: {ACTIVE_START:02d}:00 – {ACTIVE_END:02d}:00")
    cycle_num = 0

    while True:
        _wait_until_active()

        depth = random.choice([2, 3, 4])
        cycle_num += 1
        run_cycle(cycle_num, depth)

        if _is_active_hour():
            between = random.uniform(20, 120)
            print(f"\n[S3-SCHED] Waiting {between:.0f}s before next cycle...")
            time.sleep(between)


if __name__ == "__main__":
    main()
