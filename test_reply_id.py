"""
Test that _scrape_new_reply_id returns the reply's own ID, not the parent comment ID.

Steps:
  1. Posts a top-level comment on the video as account1
  2. Replies to that comment as account2
  3. Prints both IDs — they must be different
"""
import os
from dotenv import load_dotenv

load_dotenv()
os.environ["DRY_RUN"] = "False"

# Use account1 for the initial comment, account2 for the reply
ACCOUNT = os.getenv("TEST_ACCOUNT", "1")  # override with TEST_ACCOUNT=2 for reply step
VIDEO_ID = os.getenv("TEST_VIDEO_ID", "CsvHI868N6o")

# ── Step 1: post a top-level comment as account1, capture its ID ──────────────
os.environ["PROFILE_PATH"] = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")

from comment_poster import post_comment, post_reply

print(f"[TEST-REPLY-ID] Video: {VIDEO_ID}")
print()

print("[TEST-REPLY-ID] Step 1 — posting top-level comment as account1...")
parent_comment_id = post_comment(
    video_id=VIDEO_ID,
    comment_text="Testing freight consolidation options — anyone used DocShipper for this?",
    video_title="Test video",
)
print(f"[TEST-REPLY-ID] Parent comment ID: {parent_comment_id}")
print()

if not parent_comment_id or parent_comment_id.startswith("dry_run"):
    print("[TEST-REPLY-ID] ABORT — could not post parent comment")
    raise SystemExit(1)

# ── Step 2: reply to that comment as account2, capture reply ID ───────────────
import importlib, sys

# Re-import comment_poster with account2 profile
os.environ["PROFILE_PATH"] = os.getenv("PROFILE_ACCOUNT2", "profiles/account2")

# Reload so PROFILE_PATH is re-read by browser_helper
for mod in ["browser_helper", "comment_poster"]:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])

from comment_poster import post_reply  # noqa: F811 — intentional reload

print("[TEST-REPLY-ID] Step 2 — posting reply as account2...")
reply_id = post_reply(
    video_id=VIDEO_ID,
    parent_comment_id=parent_comment_id,
    reply_text="Good question — I've used them for LCL consolidation, solid experience.",
    comment_text="Testing freight consolidation options — anyone used DocShipper for this?",
)
print(f"[TEST-REPLY-ID] Reply ID: {reply_id}")
print()

# ── Verdict ───────────────────────────────────────────────────────────────────
if reply_id and reply_id != parent_comment_id:
    print("[TEST-REPLY-ID] PASS — reply ID differs from parent comment ID")
elif reply_id == parent_comment_id:
    print("[TEST-REPLY-ID] FAIL — reply ID is the same as parent comment ID (bug not fixed)")
else:
    print("[TEST-REPLY-ID] WARN — reply ID is empty (scraping failed, fallback was used)")
