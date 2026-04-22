"""Test coordination read/write directly."""
from coordination import (
    s1_add_target, s1_get_pending, s1_update, s1_get_all_ids,
    S1_FILE,
)

VIDEO_ID = "test_video_123"
VIDEO_TITLE = "Test Video Title"

print(f"[TEST] Using file: {S1_FILE}")

print("\n[TEST] Adding target...")
s1_add_target(VIDEO_ID, VIDEO_TITLE)

print("\n[TEST] Reading pending...")
target = s1_get_pending()
print(f"  pending target: {target}")

print("\n[TEST] Updating status to a_done...")
s1_update(VIDEO_ID, status="a_done", account1_comment_id="test_comment_id")

print("\n[TEST] Reading again — should show a_done...")
all_ids = s1_get_all_ids()
print(f"  all IDs: {all_ids}")

pending_after = s1_get_pending()
print(f"  pending after update: {pending_after}")

print("\n[TEST] Done. Check targets_s1.json to confirm the write.")
