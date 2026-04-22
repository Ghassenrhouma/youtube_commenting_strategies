"""
Diagnostic: navigate to a video normally, find a thread that has replies,
expand them, then dump every attribute and link we can find inside the reply
elements — so we know exactly what YouTube puts in the DOM for replies.
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
from comment_poster import _wait_for_load, _dismiss_consent_banner, _sort_comments_newest

VIDEO_ID = "IiO5gbg4dUw"

print(f"[DIAG] Navigating normally to {VIDEO_ID} (no &lc= parameter)")

with sync_playwright() as p:
    context = get_browser_context(p)
    page = context.new_page()
    patch_page(page)
    try:
        page.goto(f"https://www.youtube.com/watch?v={VIDEO_ID}")
        _wait_for_load(page)
        _dismiss_consent_banner(page)

        # Scroll until comment threads appear
        print("[DIAG] Scrolling to load comments...")
        for _ in range(25):
            if page.query_selector("ytd-comment-thread-renderer"):
                break
            page.evaluate("window.scrollBy(0, 600)")
            time.sleep(random.uniform(0.5, 1.0))

        thread_count = len(page.query_selector_all("ytd-comment-thread-renderer"))
        print(f"[DIAG] {thread_count} comment threads loaded")
        if thread_count == 0:
            print("[DIAG] ABORT — no threads found")
            raise SystemExit(1)

        # Find the first thread that has a replies expander
        print("[DIAG] Looking for a thread with replies...")
        target_thread = None
        for thread in page.query_selector_all("ytd-comment-thread-renderer"):
            has_replies = thread.evaluate("""
                el => {
                    const btns = el.querySelectorAll('button, ytd-button-renderer, #expander-header');
                    for (const b of btns) {
                        if (b.textContent.toLowerCase().includes('repl')) return true;
                    }
                    return false;
                }
            """)
            if has_replies:
                target_thread = thread
                break
            page.evaluate("window.scrollBy(0, 400)")
            time.sleep(0.3)

        if not target_thread:
            print("[DIAG] No thread with replies found — using first thread")
            target_thread = page.query_selector("ytd-comment-thread-renderer")

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
        print(f"[DIAG] Expanded: '{expanded}'")
        time.sleep(3.0)

        reply_count = len(target_thread.query_selector_all(
            "ytd-comment-replies-renderer ytd-comment-renderer, "
            "ytd-comment-replies-renderer ytd-comment-view-model"
        ))
        print(f"[DIAG] {reply_count} reply elements visible")

        # Dump every attribute + every href/link inside each reply element
        dump = target_thread.evaluate("""
            el => {
                const out = [];
                const replies = el.querySelectorAll(
                    'ytd-comment-replies-renderer ytd-comment-renderer, ' +
                    'ytd-comment-replies-renderer ytd-comment-view-model'
                );
                replies.forEach((r, i) => {
                    const info = {index: i, tag: r.tagName, attrs: {}, links: [], childIds: []};
                    for (const a of r.attributes) info.attrs[a.name] = a.value;
                    r.querySelectorAll('a[href]').forEach(a => info.links.push(a.href));
                    r.querySelectorAll('[id]').forEach(el2 => {
                        if (el2.id) info.childIds.push({id: el2.id, tag: el2.tagName, attrs: Object.fromEntries(Array.from(el2.attributes).map(a=>[a.name,a.value]))});
                    });
                    out.push(info);
                });
                return out;
            }
        """)

        print()
        print("=" * 60)
        for entry in dump:
            print(f"[REPLY {entry['index']}] <{entry['tag']}>")
            print(f"  attrs     : {entry['attrs']}")
            print(f"  links     : {entry['links'][:5]}")
            for cid in entry['childIds']:
                if any(k in cid['attrs'] for k in ('data-comment-id', 'id')) or 'comment' in cid['id'].lower():
                    print(f"  child #{cid['id']} ({cid['tag']}): {cid['attrs']}")
            print()
        print("=" * 60)

    finally:
        context.close()
