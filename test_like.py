"""Test the like button on a real video using account1."""
import os
from dotenv import load_dotenv

load_dotenv()
os.environ["PROFILE_PATH"] = os.getenv("PROFILE_ACCOUNT1", "profiles/account1")
os.environ["DRY_RUN"] = "False"

from playwright.sync_api import sync_playwright
from browser_helper import get_browser_context, patch_page
from comment_poster import _try_like_video, _navigate_to_video, _ensure_video_playing

VIDEO_ID = "CsvHI868N6o"

with sync_playwright() as p:
    context = get_browser_context(p)
    page = context.new_page()
    patch_page(page)
    try:
        print(f"[TEST-LIKE] Navigating to {VIDEO_ID}...")
        _navigate_to_video(page, VIDEO_ID)
        _ensure_video_playing(page)
        print("[TEST-LIKE] Attempting like...")
        _try_like_video(page)
    finally:
        context.close()
