import os
import random
import time
import difflib
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from browser_helper import (
    get_browser_context, patch_page,
    human_click, human_click_element, human_scroll, human_type,
)

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_watch_max_debug = os.getenv("WATCH_MAX", "NOT SET")
print(f"[CONFIG] WATCH_MAX={_watch_max_debug}")


def _wait_for_load(page, timeout=20000):
    """Wait for networkidle with a hard timeout — YouTube never fully idles."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        pass  # page is loaded enough


DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SKIP_DELAYS = os.getenv("SKIP_DELAYS", "True").lower() == "true"


def _random_imperfection(page):
    """Simulates human mistakes and corrections."""
    action = random.choice([
        "misclick_back", "reload", "pause_and_scroll",
        "nothing", "nothing", "nothing",
    ])

    if action == "misclick_back":
        try:
            page.go_back()
            time.sleep(random.uniform(1, 3))
            page.go_forward()
            time.sleep(random.uniform(1, 2))
            print("  [HUMAN] Simulated back/forward navigation")
        except Exception:
            pass

    elif action == "reload":
        try:
            page.reload()
            _wait_for_load(page)
            time.sleep(random.uniform(2, 4))
            print("  [HUMAN] Simulated page reload")
        except Exception:
            pass

    elif action == "pause_and_scroll":
        page.evaluate(f"window.scrollBy(0, {random.randint(-100, 300)})")
        time.sleep(random.uniform(2, 6))


def _search_and_click_video(page, video_id, video_title=""):
    """Types a search query and clicks the target video."""
    try:
        human_click(page, "input#search")
        time.sleep(random.uniform(0.5, 1.5))

        # Use title if available — humans never search by URL
        if video_title:
            # Occasionally shorten the query like a real user would
            words = video_title.split()
            if len(words) > 5 and random.random() < 0.4:
                query = " ".join(words[:random.randint(3, 5)])
            else:
                query = video_title
        else:
            query = video_id

        for char in query:
            page.keyboard.type(char)
            time.sleep(random.uniform(0.05, 0.15))

        time.sleep(random.uniform(0.5, 1.2))
        page.keyboard.press("Enter")
        _wait_for_load(page)
        time.sleep(random.uniform(2, 4))

        video_link = page.query_selector(f"a[href*='{video_id}']")
        if video_link:
            human_click_element(page, video_link)
            _wait_for_load(page)
        else:
            page.goto(f"https://www.youtube.com/watch?v={video_id}")
            _wait_for_load(page)

    except Exception:
        page.goto(f"https://www.youtube.com/watch?v={video_id}")
        _wait_for_load(page)


def _dismiss_consent_banner(page):
    """Dismiss YouTube's GDPR consent popup if present (common in Docker/fresh profiles)."""
    try:
        for selector in [
            "ytd-consent-bump-v2-lightbox button[aria-label*='Accept']",
            "ytd-consent-bump-v2-lightbox button[aria-label*='Agree']",
            "ytd-consent-bump-v2-lightbox .eom-buttons button:first-child",
            "button[aria-label='Accept all']",
            "button[aria-label='Agree to all']",
        ]:
            btn = page.query_selector(selector)
            if btn:
                btn.click()
                print("  [CONSENT] Dismissed consent banner")
                time.sleep(random.uniform(1.0, 2.0))
                return
        dismissed = page.evaluate("""() => {
            const lb = document.querySelector('ytd-consent-bump-v2-lightbox');
            if (!lb) return false;
            const btn = lb.querySelector('button');
            if (btn) { btn.click(); return true; }
            return false;
        }""")
        if dismissed:
            print("  [CONSENT] Dismissed consent banner via JS")
            time.sleep(random.uniform(1.0, 2.0))
    except Exception:
        pass


def _navigate_to_video(page, video_id, video_title=""):
    """Simulates a human arriving at a video naturally."""
    page.goto("https://www.youtube.com")
    _wait_for_load(page)
    time.sleep(random.uniform(3, 8))
    _dismiss_consent_banner(page)

    page.evaluate(f"window.scrollBy(0, {random.randint(200, 500)})")
    time.sleep(random.uniform(2, 5))

    if random.random() < 0.3:
        page.evaluate("window.scrollBy(0, -200)")
        time.sleep(random.uniform(1, 3))

    if random.random() < 0.5:
        _search_and_click_video(page, video_id, video_title)
    else:
        page.goto(f"https://www.youtube.com/watch?v={video_id}")
        _wait_for_load(page)

    if random.random() < 0.25:
        _random_imperfection(page)


def _is_ad_showing(page) -> bool:
    # .ad-showing on the player itself is the only reliable indicator
    # .ytp-ad-player-overlay exists in the DOM even during normal playback
    return page.evaluate("""
        () => !!document.querySelector('.html5-video-player.ad-showing')
    """)


def _handle_ads(page):
    """Wait for ads to finish. Only click skip when the button is clearly visible."""
    print("  [AD] Ad detected — waiting...")
    for _ in range(30):  # poll every 2s, up to 60s total
        if not _is_ad_showing(page):
            print("  [AD] Ad finished")
            return
        # Only click skip if the button is visible — don't touch anything else
        for selector in [".ytp-skip-ad-button", ".ytp-ad-skip-button-modern"]:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    print("  [AD] Skipping ad...")
                    human_click_element(page, btn)
                    time.sleep(random.uniform(1.5, 2.5))
                    break
            except Exception:
                pass
        time.sleep(2)


def _ensure_video_playing(page):
    """Wait for the player to load and handle any pre-roll ads. Let YouTube autoplay."""
    try:
        page.wait_for_selector(".html5-video-player", timeout=20000)
        time.sleep(random.uniform(1.5, 2.5))
        _handle_ads(page)
    except Exception:
        pass


def _is_player_error(page) -> bool:
    return page.evaluate("""
        () => {
            const err = document.querySelector('.ytp-error');
            if (!err) return false;
            const style = window.getComputedStyle(err);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
            const rect = err.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return false;
            // Must have visible error text to avoid false positives
            const msg = err.querySelector('.ytp-error-content');
            return !!msg && (msg.innerText || '').trim().length > 0;
        }
    """)


def _recover_player_error(page, video_url: str):
    """Recover from a player error by clicking the in-player retry button."""
    print("  [ERROR] Player error — clicking retry button...")
    try:
        # Try clicking the retry button — avoid <a> tags (those are "Learn more" links)
        retried = False

        # 1. Any <button> inside the error overlay
        for btn in (page.query_selector_all(".ytp-error button") or []):
            if btn.is_visible():
                human_click_element(page, btn)
                retried = True
                break

        # 2. The error content area itself is clickable for retry
        if not retried:
            el = page.query_selector(".ytp-error-content-wrap")
            if el and el.is_visible():
                human_click_element(page, el)
                retried = True

        # 3. JS: find any element inside .ytp-error whose text says retry/reload (not a link)
        if not retried:
            page.evaluate("""
                () => {
                    const err = document.querySelector('.ytp-error');
                    if (!err) return;
                    const walker = document.createTreeWalker(err, NodeFilter.SHOW_ELEMENT);
                    while (walker.nextNode()) {
                        const n = walker.currentNode;
                        if (n.tagName === 'A') continue;
                        const t = (n.innerText || '').toLowerCase();
                        if (t.includes('retry') || t.includes('reload') || t.includes('tap to')) {
                            n.click(); break;
                        }
                    }
                }
            """)
            retried = True

        if retried:
            time.sleep(random.uniform(3.0, 5.0))
            if not _is_player_error(page):
                print("  [ERROR] ✓ Retry worked")
                _ensure_video_playing(page)
                return
    except Exception:
        pass

    # Retry button didn't clear it — fall back to page reload
    print("  [ERROR] Retry button failed — reloading page...")
    page.reload()
    _wait_for_load(page)
    time.sleep(random.uniform(4.0, 7.0))
    _ensure_video_playing(page)


def _watch_with_ad_checks(page, watch_time: float):
    """Just sleep for the watch duration — no polling, no interaction."""
    time.sleep(watch_time)


def _debug_page_state(page, label="debug"):
    """Dump page URL, key element presence, screenshot and HTML to /app/code/debug/ for post-mortem."""
    try:
        import os
        out_dir = "/app/code/debug"
        os.makedirs(out_dir, exist_ok=True)
        url = page.url
        sign_in = bool(page.query_selector("a[href*='accounts.google.com'], ytd-button-renderer[id*='sign']"))
        consent = bool(page.query_selector("ytd-consent-bump-v2-lightbox"))
        textarea = bool(page.query_selector("#contenteditable-root"))
        reply_btn_present = bool(page.query_selector("#reply-button-end"))
        print(f"  [DEBUG:{label}] url={url[:80]}")
        print(f"  [DEBUG:{label}] sign_in_prompt={sign_in} consent={consent} textarea={textarea} reply_btn={reply_btn_present}")
        page.screenshot(path=f"{out_dir}/{label}.png", full_page=False)
        with open(f"{out_dir}/{label}.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"  [DEBUG:{label}] saved -> {out_dir}/{label}.png + .html")
    except Exception as e:
        print(f"  [DEBUG:{label}] failed to capture state: {e}")


def _try_like_video(page):
    """Like the video if not already liked. Tries multiple selectors."""
    try:
        like_btn = None
        for selector in [
            "#segmented-like-button button",
            "ytd-like-button-renderer button",
            "like-button-view-model button",
            "button[aria-label*='like' i]",
            "button[aria-label*='aime' i]",
        ]:
            el = page.query_selector(selector)
            if el:
                like_btn = el
                break

        if not like_btn:
            print("  [LIKE] Button not found")
            return

        # Skip if already liked
        aria_pressed = like_btn.get_attribute("aria-pressed")
        if aria_pressed == "true":
            print("  [LIKE] Already liked — skipping")
            return

        # Scroll into view — short timeout, force=True on click makes it non-blocking anyway
        try:
            like_btn.scroll_into_view_if_needed(timeout=4000)
        except Exception:
            pass
        time.sleep(random.uniform(0.8, 1.5))

        # force=True bypasses viewport/actionability checks that headless often fails
        try:
            like_btn.click(force=True)
        except Exception:
            page.evaluate("el => el.click()", like_btn)

        time.sleep(random.uniform(1.5, 2.5))
        aria_after = like_btn.get_attribute("aria-pressed")
        if aria_after == "true":
            print("  [LIKE] ✓ Liked")
        else:
            print("  [LIKE] Click sent but state unchanged — may not have registered")
    except Exception as e:
        print(f"  [LIKE] Failed: {e}")


def _get_video_duration(page) -> int:
    """Read video duration from the YouTube player. Returns seconds, or 600 as fallback."""
    # Try JS video.duration first — works in headless where DOM text may show 0:00 initially
    for attempt in range(8):
        try:
            dur = page.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : 0; }")
            if dur and dur > 0 and not (dur != dur):  # exclude 0, None, NaN
                return int(dur)
        except Exception:
            pass
        time.sleep(1)
    # Fallback: parse the DOM text element
    try:
        duration_el = page.query_selector(".ytp-time-duration")
        if duration_el:
            text = (duration_el.inner_text() or "").strip()  # e.g. "12:34" or "1:02:34"
            parts = text.split(":")
            if len(parts) == 2 and int(parts[0]) + int(parts[1]) > 0:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except Exception:
        pass
    return 600  # safe fallback


def _cap_watch_time(desired: float, duration: int) -> float:
    """Ensure watch time is at most 85% of video duration, minimum 60s.
    Respects WATCH_MAX env var if set — picks randomly up to the cap."""
    max_watch = max(60, int(duration * 0.85))
    result = min(desired, max_watch)
    watch_max_env = int(os.getenv("WATCH_MAX", "0"))
    if watch_max_env:
        result = min(result, watch_max_env)
    return result


def _variable_video_behavior(page):
    """Simulates different ways humans interact with a video before commenting."""
    _ensure_video_playing(page)
    duration = _get_video_duration(page)

    behavior = os.getenv("WATCH_BEHAVIOR") or random.choices(
        ["quick_commenter", "normal_watcher", "engaged_watcher", "skeptical_browser"],
        weights=[20, 40, 25, 15],
    )[0]

    if behavior == "quick_commenter":
        watch_time = _cap_watch_time(random.uniform(180, 300), duration)
        print(f"  [HUMAN] Quick commenter — watching {int(watch_time)}s / {duration}s")
        _watch_with_ad_checks(page, watch_time)
        if random.random() < 0.20:
            _try_like_video(page)
        page.evaluate("window.scrollBy(0, 400)")
        time.sleep(random.uniform(1, 2))

    elif behavior == "normal_watcher":
        watch_time = _cap_watch_time(random.uniform(180, 360), duration)
        print(f"  [HUMAN] Normal watcher — watching {int(watch_time)}s / {duration}s")
        _watch_with_ad_checks(page, watch_time)
        if random.random() < 0.20:
            _try_like_video(page)
        page.evaluate("window.scrollBy(0, 300)")
        time.sleep(random.uniform(2, 4))
        page.evaluate("window.scrollBy(0, 300)")
        time.sleep(random.uniform(1, 3))

    elif behavior == "engaged_watcher":
        watch_time = _cap_watch_time(random.uniform(300, 600), duration)
        print(f"  [HUMAN] Engaged watcher — watching {int(watch_time)}s / {duration}s")
        _watch_with_ad_checks(page, watch_time)
        if random.random() < 0.20:
            _try_like_video(page)
        try:
            human_click(page, "tp-yt-paper-button#expand")
            time.sleep(random.uniform(2, 5))
        except Exception:
            pass
        page.evaluate("window.scrollBy(0, 400)")
        time.sleep(random.uniform(2, 4))

    elif behavior == "skeptical_browser":
        watch_time = _cap_watch_time(random.uniform(180, 360), duration)
        print(f"  [HUMAN] Skeptical browser — watching {int(watch_time)}s / {duration}s")
        _watch_with_ad_checks(page, watch_time)
        if random.random() < 0.20:
            _try_like_video(page)
        page.evaluate("window.scrollBy(0, 500)")
        time.sleep(random.uniform(2, 4))
        page.evaluate("window.scrollBy(0, -200)")
        time.sleep(random.uniform(1, 3))
        page.evaluate("window.scrollBy(0, 300)")
        time.sleep(random.uniform(1, 2))


def _type_reply(page, text):
    """Human-paced typing for reply boxes (element already focused)."""
    words = text.split(" ")
    total_words = len(words)

    for word_idx, word in enumerate(words):
        for char in word:
            page.keyboard.type(char)
            # Slower base: gauss centred at 0.13s
            delay = max(0.04, min(0.40, random.gauss(0.13, 0.05)))
            if char in ".,!?;:":
                # Re-reads after punctuation
                delay += random.uniform(0.20, 0.55)
            # Occasional typo: wrong char then backspace
            if char.isalpha() and random.random() < 0.025:
                time.sleep(delay)
                page.keyboard.type(random.choice("abcdefghijklmnopqrstuvwxyz"))
                time.sleep(random.uniform(0.15, 0.40))
                page.keyboard.press("Backspace")
                time.sleep(random.uniform(0.08, 0.22))
                page.keyboard.type(char)
                delay = random.uniform(0.06, 0.18)
            time.sleep(delay)

        if word_idx < total_words - 1:
            page.keyboard.type(" ")
            roll = random.random()
            if roll < 0.10:
                # "Thinking" pause — writer stops to consider next word
                time.sleep(random.uniform(1.0, 2.2))
            elif roll < 0.25:
                # Short hesitation
                time.sleep(random.uniform(0.35, 0.80))
            else:
                time.sleep(random.uniform(0.05, 0.18))

        # Mid-sentence thinking stop every ~8-14 words
        if word_idx > 0 and word_idx % random.randint(8, 14) == 0:
            time.sleep(random.uniform(1.2, 2.5))


def passive_browse_session(page=None):
    """Simulates a human casually browsing YouTube between comment sessions."""
    if DRY_RUN:
        print("  [HUMAN] DRY RUN: Would browse YouTube passively")
        return

    def _browse(pg):
        pg.goto("https://www.youtube.com")
        _wait_for_load(pg)
        time.sleep(random.uniform(3, 7))

        for _ in range(random.randint(2, 4)):
            pg.evaluate(f"window.scrollBy(0, {random.randint(200, 400)})")
            time.sleep(random.uniform(1.5, 4.0))

        video_links = pg.query_selector_all("ytd-rich-item-renderer a#video-title-link")
        if video_links:
            random_video = random.choice(video_links[:8])
            human_click_element(pg, random_video)
            _wait_for_load(pg)

            _ensure_video_playing(pg)
            _watch_max = int(os.getenv("WATCH_MAX", "0"))
            watch_time = min(random.uniform(30, 90), _watch_max) if _watch_max else random.uniform(30, 90)
            print(f"  [HUMAN] Passively watching random video for {int(watch_time)}s")
            _watch_with_ad_checks(pg, watch_time)

            pg.evaluate("window.scrollBy(0, 300)")
            time.sleep(random.uniform(2, 5))

            if random.random() < 0.2:
                pg.go_back()
                time.sleep(random.uniform(2, 4))
                video_links2 = pg.query_selector_all("ytd-rich-item-renderer a#video-title-link")
                if video_links2:
                    choice = random.choice(video_links2[:8])
                    human_click_element(pg, choice)
                    _wait_for_load(pg)
                    _ensure_video_playing(pg)
                    _watch_with_ad_checks(pg, random.uniform(20, 60))

    if page is not None:
        _browse(page)
        return

    with sync_playwright() as p:
        context = get_browser_context(p)
        pg = context.new_page()
        patch_page(pg)
        try:
            _browse(pg)
        finally:
            context.close()


def _scrape_new_comment_id(page) -> str:
    """Scrape the real YouTube comment ID of the most recently posted comment."""
    try:
        # Scroll back to top of comments where new comment appears
        page.evaluate("document.querySelector('#comments')?.scrollIntoView()")
        time.sleep(random.uniform(1.5, 2.5))

        # Try to find comment ID from the first comment thread
        comment_id = page.evaluate("""
            () => {
                const threads = document.querySelectorAll('ytd-comment-thread-renderer');
                for (const thread of threads) {
                    const el = thread.querySelector('#comment');
                    if (el) {
                        // Try data attribute first
                        const id = el.getAttribute('data-comment-id') ||
                                   thread.getAttribute('data-comment-id');
                        if (id) return id;
                        // Try extracting from anchor href inside the thread
                        const link = thread.querySelector('a[href*="lc="]');
                        if (link) {
                            const match = link.href.match(/lc=([^&]+)/);
                            if (match) return match[1];
                        }
                    }
                }
                return null;
            }
        """)
        if comment_id:
            print(f"  [COMMENT ID] Scraped: {comment_id}")
        return comment_id or ""
    except Exception as e:
        print(f"  [COMMENT ID] Could not scrape: {e}")
        return ""


def post_comment(video_id: str, comment_text: str, page=None, video_title: str = "") -> str:
    if DRY_RUN:
        print(f"[DRY RUN] Would post comment on {video_id}:")
        print(f"  '{comment_text}'")
        return "dry_run_comment_id"

    def _execute(pg):
        _navigate_to_video(pg, video_id, video_title)
        _variable_video_behavior(pg)

        if f"watch?v={video_id}" not in pg.url:
            print(f"  [WARN] Autoplay navigated away — returning to target video")
            pg.goto(f"https://www.youtube.com/watch?v={video_id}")
            _wait_for_load(pg)
            time.sleep(random.uniform(2, 4))

        human_scroll(pg)

        # In headless Docker, scroll aggressively to trigger YouTube's Intersection Observer
        # which lazy-loads the comments section
        pg.evaluate("""
            () => {
                const c = document.querySelector('ytd-comments') || document.querySelector('#comments');
                if (c) c.scrollIntoView({behavior: 'instant', block: 'start'});
                else window.scrollTo(0, Math.floor(document.body.scrollHeight * 0.6));
            }
        """)
        time.sleep(random.uniform(2.0, 3.0))
        pg.evaluate("window.scrollBy(0, 300)")
        time.sleep(random.uniform(1.0, 2.0))

        try:
            pg.wait_for_selector("#simplebox-placeholder", timeout=30000)
        except PlaywrightTimeoutError:
            _debug_page_state(pg, "no_simplebox")
            raise Exception("Comment box not found — cookies may be expired")

        # Scroll placeholder to center of viewport
        pg.evaluate("""
            () => {
                const el = document.querySelector('#simplebox-placeholder');
                if (el) el.scrollIntoView({behavior: 'instant', block: 'center'});
            }
        """)
        time.sleep(random.uniform(1.0, 1.5))

        # Attempt 1: human bezier click
        human_click(pg, "#simplebox-placeholder")
        time.sleep(random.uniform(1.5, 2.5))

        # Attempt 2: Playwright direct click with force
        if not pg.query_selector("#contenteditable-root"):
            try:
                pg.click("#simplebox-placeholder", force=True)
            except Exception:
                pass
            time.sleep(random.uniform(1.0, 1.5))

        # Attempt 3: Full MouseEvent dispatch — required for YouTube's custom elements
        if not pg.query_selector("#contenteditable-root"):
            pg.evaluate("""
                () => {
                    const el = document.querySelector('#simplebox-placeholder');
                    if (!el) return;
                    const opts = {bubbles: true, cancelable: true, view: window};
                    el.dispatchEvent(new MouseEvent('mouseover', opts));
                    el.dispatchEvent(new MouseEvent('mouseenter', opts));
                    el.dispatchEvent(new MouseEvent('mousedown', opts));
                    el.dispatchEvent(new MouseEvent('mouseup', opts));
                    el.dispatchEvent(new MouseEvent('click', opts));
                }
            """)
            time.sleep(random.uniform(1.5, 2.5))

        # Attempt 4: Click the parent renderer + try focusing any contenteditable inside it
        if not pg.query_selector("#contenteditable-root"):
            pg.evaluate("""
                () => {
                    const renderer = document.querySelector('ytd-comment-simplebox-renderer');
                    if (!renderer) return;
                    const opts = {bubbles: true, cancelable: true, view: window};
                    renderer.dispatchEvent(new MouseEvent('click', opts));
                    const inner = renderer.querySelector('[contenteditable], [id*="placeholder"]');
                    if (inner) { inner.dispatchEvent(new MouseEvent('click', opts)); inner.focus(); }
                }
            """)
            time.sleep(random.uniform(1.5, 2.5))

        try:
            pg.wait_for_selector("#contenteditable-root", timeout=15000)
        except PlaywrightTimeoutError:
            _debug_page_state(pg, "comment_box_fail")
            raise Exception("Comment input did not open — YouTube may have blocked the interaction")

        time.sleep(random.uniform(1.0, 2.5))

        human_type(pg, "#contenteditable-root", comment_text)
        time.sleep(random.uniform(1.5, 3.0))

        submit_btn = pg.query_selector("ytd-commentbox #submit-button")
        if not submit_btn:
            submit_btn = pg.query_selector("#submit-button")
        human_click_element(pg, submit_btn)
        time.sleep(random.uniform(3.0, 5.0))

        return _scrape_new_comment_id(pg) or f"posted_{video_id}_{int(time.time())}"

    if page is not None:
        return _execute(page)

    with sync_playwright() as p:
        context = get_browser_context(p)
        try:
            pg = context.new_page()
            patch_page(pg)
            return _execute(pg)
        finally:
            context.close()


def _sort_comments_newest(page):
    """Switch the YouTube comment sort order to 'Newest first'."""
    try:
        # Scroll the comments section into view
        page.evaluate("""
            () => {
                const el = document.querySelector('ytd-comments') ||
                           document.querySelector('#comments');
                if (el) el.scrollIntoView({behavior: 'instant', block: 'start'});
            }
        """)
        time.sleep(random.uniform(1.0, 1.8))

        # Find and click the sort dropdown button
        sort_btn = None
        for sel in [
            "ytd-comments ytd-sort-filter-sub-menu #label",
            "ytd-sort-filter-sub-menu yt-sort-filter-sub-menu-renderer #label",
            "#sort-menu yt-sort-filter-sub-menu-renderer #label",
            "ytd-comments #sort-menu #label",
        ]:
            sort_btn = page.query_selector(sel)
            if sort_btn:
                break

        if not sort_btn:
            print("  [REPLY] Could not find sort button — continuing with default order")
            return

        sort_btn.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.4, 0.8))
        sort_btn.evaluate("el => el.click()")
        # Wait for dropdown to animate open
        time.sleep(random.uniform(1.5, 2.5))

        # Use JS to find any clickable element containing "newest" or French equivalent
        clicked = page.evaluate("""
            () => {
                const candidates = document.querySelectorAll(
                    'ytd-menu-service-item-renderer, tp-yt-paper-item, yt-list-item-view-model'
                );
                for (const el of candidates) {
                    const t = el.textContent.toLowerCase();
                    if (el.offsetParent !== null && (
                        t.includes('newest') || t.includes('r\u00e9cent') || t.includes('recent')
                    )) {
                        el.click();
                        return el.textContent.trim();
                    }
                }
                return null;
            }
        """)
        if clicked:
            time.sleep(random.uniform(1.5, 2.5))
            page.wait_for_selector("ytd-comment-thread-renderer", timeout=25000)
            print(f"  [REPLY] Sorted by: '{clicked[:40]}'")
        else:
            # Debug: print what options are actually in the dropdown
            found = page.evaluate("""
                () => {
                    const els = document.querySelectorAll(
                        'ytd-menu-service-item-renderer, tp-yt-paper-item, yt-list-item-view-model'
                    );
                    return Array.from(els).map(e => e.textContent.trim()).filter(t => t.length > 0);
                }
            """)
            print(f"  [REPLY] Sort option not found. Dropdown items: {found}")
    except Exception as e:
        print(f"  [REPLY] Sort switch failed ({e}) — continuing with default order")


def post_reply(video_id: str, parent_comment_id: str, reply_text: str, comment_text: str = "", top_level_comment_text: str = "") -> str:
    if DRY_RUN:
        print(f"[DRY RUN] Would reply to comment on {video_id}:")
        print(f"  '{reply_text}'")
        return "dry_run_reply_id"

    with sync_playwright() as p:
        context = get_browser_context(p)
        try:
            page = context.new_page()
            patch_page(page)

            # ── Account 3 flow: find top-level comment → expand replies → find reply ──
            if top_level_comment_text:
                page.goto(f"https://www.youtube.com/watch?v={video_id}")
                _wait_for_load(page)
                _dismiss_consent_banner(page)
                _variable_video_behavior(page)

                # Guard against autoplay navigating away
                if f"watch?v={video_id}" not in page.url:
                    page.goto(f"https://www.youtube.com/watch?v={video_id}")
                    _wait_for_load(page)
                    _dismiss_consent_banner(page)
                # Scroll just enough to bring ytd-comments into view for the sort button
                for _ in range(15):
                    if page.query_selector("ytd-comments ytd-sort-filter-sub-menu, ytd-sort-filter-sub-menu"):
                        break
                    page.evaluate("window.scrollBy(0, 600)")
                    time.sleep(random.uniform(0.5, 1.0))

                # Switch filter FIRST — on some videos comments only load after this
                _sort_comments_newest(page)
                time.sleep(random.uniform(1.5, 2.5))

                # Now scroll to load comment threads
                for i in range(30):
                    count = len(page.query_selector_all("ytd-comment-thread-renderer"))
                    if count > 0:
                        print(f"  [DEBUG] Comments loaded: {count} threads after {i} scrolls")
                        break
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(random.uniform(0.8, 1.5))

                if not page.query_selector("ytd-comment-thread-renderer"):
                    raise Exception("Comments section never loaded — aborting")
                time.sleep(random.uniform(1.0, 2.0))

                # Find top-level thread by similarity
                norm_top = " ".join(top_level_comment_text[:120].lower().split())
                top_thread = None
                best_ratio = 0.0
                best_thread = None
                for scroll_attempt in range(30):
                    for thread in page.query_selector_all("ytd-comment-thread-renderer"):
                        text_el = thread.query_selector("#content-text, yt-formatted-string#content-text")
                        t = " ".join((text_el.inner_text() or "").lower().split()) if text_el else ""
                        ratio = difflib.SequenceMatcher(None, norm_top, t[:len(norm_top)+40]).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_thread = thread
                        if ratio >= 0.70:
                            top_thread = thread
                            print(f"  [REPLY] Found top-level comment ({ratio:.2f})")
                            break
                    if top_thread:
                        break
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(random.uniform(1.0, 2.0))
                if not top_thread and best_thread and best_ratio >= 0.40:
                    print(f"  [REPLY] Using best top-level match ({best_ratio:.2f})")
                    top_thread = best_thread
                if not top_thread:
                    raise Exception("Top-level comment not found — aborting")

                # Expand replies by clicking the "X replies" button
                top_thread.scroll_into_view_if_needed()
                time.sleep(random.uniform(0.8, 1.2))

                # Use JS to find and click the replies expander within this thread
                expanded = top_thread.evaluate("""
                    el => {
                        const btns = el.querySelectorAll('button, ytd-button-renderer, #expander-header');
                        for (const b of btns) {
                            const t = b.textContent.toLowerCase();
                            if (t.includes('repl') || t.includes('r\u00e9ponse')) {
                                b.click();
                                return b.textContent.trim();
                            }
                        }
                        return null;
                    }
                """)
                if expanded:
                    print(f"  [REPLY] Clicked expand button: '{expanded[:60]}'")
                else:
                    print("  [REPLY] No expand button found — replies may already be visible")
                time.sleep(random.uniform(2.0, 3.0))

                # Wait for replies to appear in the page
                try:
                    page.wait_for_selector(
                        "ytd-comment-replies-renderer ytd-comment-renderer, "
                        "ytd-comment-replies-renderer ytd-comment-view-model",
                        timeout=8000
                    )
                except Exception:
                    pass
                time.sleep(random.uniform(0.5, 1.0))

                # Find account2's reply by similarity — query at page level inside thread
                norm_reply = " ".join(comment_text[:120].lower().split()) if comment_text else ""
                target_reply = None
                best_reply_ratio = 0.0
                best_reply_el = None

                for attempt in range(8):
                    # Try both old and new YouTube reply element names
                    reply_renderers = top_thread.query_selector_all(
                        "ytd-comment-replies-renderer ytd-comment-renderer, "
                        "ytd-comment-replies-renderer ytd-comment-view-model"
                    )
                    print(f"  [REPLY] {len(reply_renderers)} replies visible (attempt {attempt})")
                    for rr in reply_renderers:
                        text_el = rr.query_selector(
                            "#content-text, yt-formatted-string#content-text, "
                            "#body #main #content #content-text"
                        )
                        rr_text = " ".join((text_el.inner_text() or "").lower().split()) if text_el else ""
                        if not rr_text:
                            # fallback: grab all text from the renderer
                            rr_text = " ".join((rr.inner_text() or "").lower().split())[:200]
                        ratio = difflib.SequenceMatcher(None, norm_reply, rr_text[:len(norm_reply)+40]).ratio()
                        if ratio > best_reply_ratio:
                            best_reply_ratio = ratio
                            best_reply_el = rr
                            print(f"  [REPLY] Best so far ({ratio:.2f}): '{rr_text[:60]}'")
                        if ratio >= 0.55:
                            target_reply = rr
                            print(f"  [REPLY] Matched reply ({ratio:.2f})")
                            break
                    if target_reply:
                        break
                    more_btn = top_thread.query_selector(
                        "ytd-comment-replies-renderer #more-replies button, "
                        "ytd-comment-replies-renderer ytd-button-renderer button"
                    )
                    if more_btn:
                        more_btn.evaluate("el => el.click()")
                        time.sleep(random.uniform(1.5, 2.5))
                    else:
                        time.sleep(random.uniform(0.8, 1.2))

                if not target_reply and best_reply_el and best_reply_ratio >= 0.35:
                    print(f"  [REPLY] Using best reply match ({best_reply_ratio:.2f})")
                    target_reply = best_reply_el
                if not target_reply:
                    raise Exception("Target reply not found in thread — aborting")

                target_reply.scroll_into_view_if_needed()
                time.sleep(random.uniform(0.5, 1.0))
                reply_btn = target_reply.query_selector("#reply-button-end")
                if not reply_btn:
                    raise Exception("Reply button not found on target reply")
                human_click_element(page, reply_btn)
                time.sleep(random.uniform(1.0, 2.0))

                input_el = top_thread.query_selector("ytd-comment-replies-renderer #contenteditable-root")
                if not input_el:
                    page.wait_for_selector("#contenteditable-root", timeout=20000)
                    input_el = page.query_selector("#contenteditable-root")
                human_click_element(page, input_el)
                time.sleep(random.uniform(0.5, 1.0))
                _type_reply(page, reply_text)
                time.sleep(random.uniform(1.5, 3.0))

                submit_btn = top_thread.query_selector("ytd-comment-replies-renderer #submit-button")
                if not submit_btn:
                    submit_btn = page.query_selector("#submit-button")
                if not submit_btn:
                    raise Exception("Submit button not found")
                human_click_element(page, submit_btn)
                time.sleep(random.uniform(3.0, 5.0))
                return _scrape_new_comment_id(page) or f"reply_{parent_comment_id}_{int(time.time())}"

            # ── Default flow (account 2 replying to account 1's top-level comment) ──
            # Navigate directly to the video with the target comment highlighted
            page.goto(f"https://www.youtube.com/watch?v={video_id}&lc={parent_comment_id}")
            _wait_for_load(page)
            _dismiss_consent_banner(page)
            _variable_video_behavior(page)
            human_scroll(page)

            # Scroll progressively to trigger comment lazy-loading
            for _ in range(15):
                if page.query_selector("ytd-sort-filter-sub-menu, ytd-comment-thread-renderer"):
                    break
                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(random.uniform(0.5, 1.0))

            _sort_comments_newest(page)
            time.sleep(random.uniform(1.0, 2.0))

            for _ in range(20):
                if page.query_selector("ytd-comment-thread-renderer"):
                    break
                page.evaluate("window.scrollBy(0, 800)")
                time.sleep(random.uniform(0.8, 1.5))

            time.sleep(random.uniform(0.5, 1.5))

            target_thread = None

            # Primary: find the highlighted comment thread (loaded via &lc=)
            for attempt in range(10):
                highlighted = page.query_selector(
                    "ytd-comment-thread-renderer[is-highlighted], "
                    "ytd-comment-thread-renderer.iron-selected"
                )
                if highlighted:
                    target_thread = highlighted
                    print(f"  [REPLY] Found highlighted comment (attempt {attempt})")
                    break
                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(random.uniform(1.0, 1.8))

            # Fallback: sort newest + similarity search (handles typos from human_type)
            if not target_thread:
                _sort_comments_newest(page)
                norm_snippet = " ".join(comment_text[:120].lower().split()) if comment_text else ""
                print(f"  [REPLY] Fallback similarity search for: '{comment_text[:80]}'")
                best_thread = None
                best_ratio = 0.0
                for scroll_attempt in range(30):
                    threads = page.query_selector_all("ytd-comment-thread-renderer")
                    for thread in threads:
                        text_el = thread.query_selector("#content-text, yt-formatted-string#content-text")
                        thread_text = (text_el.inner_text() or "").strip() if text_el else ""
                        norm_thread = " ".join(thread_text.lower().split())
                        ratio = difflib.SequenceMatcher(None, norm_snippet, norm_thread[:len(norm_snippet)+40]).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_thread = thread
                        if ratio >= 0.70:
                            print(f"  [REPLY] Similarity match ({ratio:.2f}) on attempt {scroll_attempt}: '{thread_text[:80]}'")
                            target_thread = thread
                            break
                    if target_thread:
                        break
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(random.uniform(1.0, 2.0))
                # Accept best match above 0.55 if nothing hit 0.70
                if not target_thread and best_thread and best_ratio >= 0.55:
                    print(f"  [REPLY] Using best similarity match ({best_ratio:.2f})")
                    target_thread = best_thread

            if not target_thread:
                print(f"  [REPLY] ✗ Target comment not found — aborting")
                raise Exception("Target comment not found in page — not posting to avoid misfire")

            target_thread.scroll_into_view_if_needed()
            time.sleep(random.uniform(0.5, 1.0))

            reply_btn = target_thread.query_selector("#reply-button-end")
            if not reply_btn:
                raise Exception("Reply button not found on target comment")
            human_click_element(page, reply_btn)
            time.sleep(random.uniform(1.0, 2.0))

            input_el = target_thread.query_selector("#contenteditable-root")
            if not input_el:
                target_thread.wait_for_selector("#contenteditable-root", timeout=20000)
                input_el = target_thread.query_selector("#contenteditable-root")

            human_click_element(page, input_el)
            time.sleep(random.uniform(0.5, 1.0))

            _type_reply(page, reply_text)
            time.sleep(random.uniform(1.5, 3.0))

            submit_btn = target_thread.query_selector("#submit-button")
            if not submit_btn:
                raise Exception("Submit button not found in reply box")
            human_click_element(page, submit_btn)
            time.sleep(random.uniform(3.0, 5.0))

            return _scrape_new_comment_id(page) or f"reply_{parent_comment_id}_{int(time.time())}"
        finally:
            context.close()


def scrape_and_reply(video_id: str, video_title: str, is_replyable_fn, generate_reply_fn, page=None) -> dict:
    """
    Scrape comments and post a reply in a single browser session.
    Returns {"comment_text": ..., "reply_text": ..., "comment_id": ...}
    Raises Exception if no replyable comment is found or DRY_RUN is True.
    """
    if DRY_RUN:
        raise Exception("DRY_RUN=True — scrape_and_reply skipped")

    def _execute(pg):
        _navigate_to_video(pg, video_id, video_title)
        _variable_video_behavior(pg)

        if f"watch?v={video_id}" not in pg.url:
            print(f"  [WARN] Autoplay navigated away — returning to target video")
            pg.goto(f"https://www.youtube.com/watch?v={video_id}")
            _wait_for_load(pg)
            _dismiss_consent_banner(pg)
            time.sleep(random.uniform(2, 4))

        human_scroll(pg)

        # Scroll progressively to trigger comment lazy-loading
        for _ in range(15):
            if pg.query_selector("ytd-sort-filter-sub-menu, ytd-comment-thread-renderer"):
                break
            pg.evaluate("window.scrollBy(0, 600)")
            time.sleep(random.uniform(0.5, 1.0))

        # Sort by newest so fresh comments surface (helps find replyable ones)
        _sort_comments_newest(pg)
        time.sleep(random.uniform(1.0, 2.0))

        for _ in range(20):
            if pg.query_selector("ytd-comment-thread-renderer"):
                break
            pg.evaluate("window.scrollBy(0, 800)")
            time.sleep(random.uniform(0.8, 1.5))

        if not pg.query_selector("ytd-comment-thread-renderer"):
            raise Exception("Comments never loaded on this video")

        target_thread = None
        target_text = ""
        seen_threads = set()

        for scroll_attempt in range(15):
            threads = pg.query_selector_all("ytd-comment-thread-renderer")
            candidates = []
            for thread in threads:
                tid = id(thread)
                if tid in seen_threads:
                    continue
                seen_threads.add(tid)
                text_el = thread.query_selector("#content-text")
                text = (text_el.inner_text() or "").strip() if text_el else ""
                like_el = thread.query_selector("#vote-count-middle")
                like_text = (like_el.inner_text() or "").strip() if like_el else ""
                try:
                    likes = int(like_text.replace(",", "")) if like_text else 0
                except ValueError:
                    likes = 0
                if text and is_replyable_fn(text):
                    candidates.append((likes, text, thread))

            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                _, target_text, target_thread = candidates[0]
                print(f"  [REPLY] Found replyable comment (scroll {scroll_attempt}): '{target_text[:80]}'")
                break

            pg.evaluate("window.scrollBy(0, 600)")
            time.sleep(random.uniform(1.0, 2.0))

        if not target_thread:
            raise Exception("No replyable comments found on this video")

        reply_text = generate_reply_fn(video_title, target_text)
        print(f"  [REPLY] Generated reply: '{reply_text[:100]}'")

        target_thread.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.5, 1.0))

        # Hover over the comment body first — YouTube only shows the Reply button on hover
        comment_body = target_thread.query_selector("#body, #main, ytd-comment-renderer")
        if comment_body:
            try:
                comment_body.hover()
                time.sleep(random.uniform(0.4, 0.7))
            except Exception:
                pass

        reply_btn = target_thread.query_selector("#reply-button-end")
        if not reply_btn:
            raise Exception("Reply button not found on target comment")

        # Hover then click using real mouse coordinates — YouTube's reply box
        # requires a proper pointer interaction sequence to open the textarea
        reply_btn.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.6, 1.0))
        bbox = reply_btn.bounding_box()
        if bbox:
            cx = bbox["x"] + bbox["width"] / 2
            cy = bbox["y"] + bbox["height"] / 2
            pg.mouse.move(cx, cy)
            time.sleep(random.uniform(0.2, 0.4))
            pg.mouse.click(cx, cy)
        else:
            reply_btn.click(force=True)
        time.sleep(random.uniform(4.0, 6.0))  # VPN adds latency — give YouTube time to open textarea

        # Diagnose what's on the page before waiting
        _debug_page_state(pg, "after_reply_btn_click")

        # Reply box may render inside or outside the thread element — try both
        input_el = target_thread.query_selector("#contenteditable-root")
        if not input_el:
            try:
                _dismiss_consent_banner(pg)
                pg.wait_for_selector(
                    "ytd-comment-simplebox-renderer #contenteditable-root, "
                    "#reply-dialog #contenteditable-root, "
                    "#contenteditable-root",
                    timeout=25000,
                    state="attached",
                )
            except Exception as wait_err:
                # Capture diagnostic screenshot before retry
                _debug_page_state(pg, "reply_textarea_timeout")
                # Retry with mouse click
                _dismiss_consent_banner(pg)
                if bbox:
                    pg.mouse.move(cx, cy)
                    time.sleep(0.2)
                    pg.mouse.click(cx, cy)
                else:
                    reply_btn.click(force=True)
                time.sleep(random.uniform(4.0, 6.0))
                pg.wait_for_selector("#contenteditable-root", timeout=20000, state="attached")
            input_el = (
                target_thread.query_selector("#contenteditable-root")
                or pg.query_selector(
                    "ytd-comment-simplebox-renderer #contenteditable-root, "
                    "#reply-dialog #contenteditable-root, "
                    "#contenteditable-root"
                )
            )

        pg.evaluate("el => { el.focus(); el.click(); }", input_el)
        time.sleep(random.uniform(0.5, 1.0))

        _type_reply(pg, reply_text)
        time.sleep(random.uniform(1.5, 3.0))

        submit_btn = target_thread.query_selector("#submit-button")
        if not submit_btn:
            submit_btn = pg.query_selector("#submit-button")
        if not submit_btn:
            raise Exception("Submit button not found in reply box")
        submit_btn.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.3, 0.6))
        submit_btn.click(force=True)

        # Wait and verify the reply input cleared (confirms submission went through)
        time.sleep(random.uniform(5.0, 8.0))
        input_after = target_thread.query_selector("#contenteditable-root")
        if input_after:
            text_after = (input_after.inner_text() or "").strip()
            if text_after:
                raise Exception("Reply box still has content after submit — post may have failed")

        print(f"  [REPLY] ✓ Submission confirmed (input cleared)")

        scraped_id = _scrape_new_comment_id(pg)
        return {
            "comment_text": target_text,
            "reply_text": reply_text,
            "comment_id": scraped_id or f"reply_{video_id}_{int(time.time())}",
        }

    if page is not None:
        return _execute(page)

    with sync_playwright() as p:
        context = get_browser_context(p)
        try:
            pg = context.new_page()
            patch_page(pg)
            return _execute(pg)
        finally:
            context.close()


def random_human_action(video_id: str, page=None):
    action = random.choice(["like", "scroll_only", "scroll_only", "nothing"])

    if DRY_RUN:
        print(f"[DRY RUN] Would perform action '{action}' on {video_id}")
        return

    if action == "nothing":
        return

    def _act(pg):
        pg.goto(f"https://www.youtube.com/watch?v={video_id}")
        _wait_for_load(pg)
        _ensure_video_playing(pg)
        time.sleep(random.uniform(20, 45))
        if action == "like":
            _try_like_video(pg)
        elif action == "scroll_only":
            human_scroll(pg)
            time.sleep(random.uniform(5, 15))

    if page is not None:
        _act(page)
        return

    with sync_playwright() as p:
        context = get_browser_context(p)
        try:
            pg = context.new_page()
            patch_page(pg)
            _act(pg)
        finally:
            context.close()


def safe_delay(page=None):
    if SKIP_DELAYS:
        print("  [DELAY] Skipped (SKIP_DELAYS=True)")
        return

    # Allow per-account delay override via env vars (in seconds)
    delay_min = int(os.getenv("DELAY_MIN", "0"))
    delay_max = int(os.getenv("DELAY_MAX", "0"))

    if delay_min and delay_max:
        delay = random.uniform(delay_min, delay_max)
    else:
        hour = datetime.now().hour
        active = (9 <= hour < 12) or (14 <= hour < 18) or (20 <= hour < 22)
        # New account: minimum 10 min during active hours, 20 min off-peak
        delay = random.uniform(600, 1500) if active else random.uniform(1200, 2400)
        # 20% chance of a longer "got distracted" pause
        if random.random() < 0.20:
            extra = random.uniform(600, 1800)
            delay += extra

    if page is not None:
        # Split: 30-60% on the current video page, rest on YouTube home
        split = random.uniform(0.30, 0.60)
        on_video = delay * split
        on_home = delay - on_video
        print(f"  [DELAY] {delay:.0f}s split — {on_video:.0f}s on video page, {on_home:.0f}s on home")
        time.sleep(on_video)
        try:
            page.goto("https://www.youtube.com")
            _wait_for_load(page)
            # Idle on home page with occasional scrolls
            home_end = time.time() + on_home
            while time.time() < home_end:
                chunk = min(random.uniform(40, 120), home_end - time.time())
                if chunk > 0:
                    time.sleep(chunk)
                if time.time() < home_end:
                    page.evaluate(f"window.scrollBy(0, {random.randint(100, 400)})")
        except Exception:
            time.sleep(on_home)
    else:
        print(f"  [DELAY] Waiting {delay:.0f}s ({delay/60:.1f} min)...")
        time.sleep(delay)


