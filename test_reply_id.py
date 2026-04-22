"""
Test that _scrape_new_reply_id returns the reply's own ID, not the parent comment ID.

Uses a video+comment that already has replies in targets_s1.json — no new posting needed.
Just opens the thread, expands replies, and checks what ID the scraper returns.
"""
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()
os.environ["DRY_RUN"] = "False"
os.environ["PROFILE_PATH"] = os.getenv("PROFILE_ACCOUNT2", "profiles/account2")

from playwright.sync_api import sync_playwright
from browser_helper import get_browser_context, patch_page
from comment_poster import (
    _navigate_to_video, _wait_for_load, _dismiss_consent_banner,
    _sort_comments_newest, _scrape_new_reply_id,
)

# A video+comment known to have replies (from targets_s1.json)
VIDEO_ID = "IiO5gbg4dUw"
PARENT_COMMENT_ID = "UgwGYnMqVozNLIEveNt4AaABAg"
PARENT_COMMENT_TEXT = "I tried handling a ChinatoUS shipment myself"

print(f"[TEST-REPLY-ID] Video:  {VIDEO_ID}")
print(f"[TEST-REPLY-ID] Parent: {PARENT_COMMENT_ID}")
print()

with sync_playwright() as p:
    context = get_browser_context(p)
    page = context.new_page()
    patch_page(page)
    try:
        page.goto(f"https://www.youtube.com/watch?v={VIDEO_ID}&lc={PARENT_COMMENT_ID}")
        _wait_for_load(page)
        _dismiss_consent_banner(page)

        # Scroll to load comments
        for _ in range(20):
            if page.query_selector("ytd-comment-thread-renderer"):
                break
            page.evaluate("window.scrollBy(0, 600)")
            time.sleep(random.uniform(0.5, 1.0))

        # Find the target thread
        target_thread = None
        for _ in range(10):
            highlighted = page.query_selector(
                "ytd-comment-thread-renderer[is-highlighted], "
                "ytd-comment-thread-renderer.iron-selected"
            )
            if highlighted:
                target_thread = highlighted
                print("[TEST-REPLY-ID] Found highlighted thread")
                break
            page.evaluate("window.scrollBy(0, 600)")
            time.sleep(random.uniform(0.8, 1.2))

        if not target_thread:
            # fallback: first thread
            target_thread = page.query_selector("ytd-comment-thread-renderer")
            print("[TEST-REPLY-ID] Using first thread as fallback")

        if not target_thread:
            print("[TEST-REPLY-ID] ABORT — could not find comment thread")
            raise SystemExit(1)

        # Expand replies
        expanded = target_thread.evaluate("""
            el => {
                const btns = el.querySelectorAll('button, ytd-button-renderer, #expander-header');
                for (const b of btns) {
                    const t = b.textContent.toLowerCase();
                    if (t.includes('repl') || t.includes('réponse')) {
                        b.click();
                        return b.textContent.trim();
                    }
                }
                return null;
            }
        """)
        print(f"[TEST-REPLY-ID] Expand button: '{expanded}'")
        time.sleep(random.uniform(2.0, 3.0))

        # Count visible replies
        reply_count = len(target_thread.query_selector_all(
            "ytd-comment-replies-renderer ytd-comment-renderer, "
            "ytd-comment-replies-renderer ytd-comment-view-model"
        ))
        print(f"[TEST-REPLY-ID] Replies visible: {reply_count}")

        # Run the scraper
        reply_id = _scrape_new_reply_id(page, target_thread)
        print(f"[TEST-REPLY-ID] Scraped reply ID : {reply_id}")
        print(f"[TEST-REPLY-ID] Parent comment ID: {PARENT_COMMENT_ID}")
        print()

        if reply_id and reply_id != PARENT_COMMENT_ID:
            print("[TEST-REPLY-ID] PASS — reply ID differs from parent ID")
        elif reply_id == PARENT_COMMENT_ID:
            print("[TEST-REPLY-ID] FAIL — still returning parent ID (bug not fixed)")
        else:
            print("[TEST-REPLY-ID] WARN — scraper returned empty string")
    finally:
        context.close()
