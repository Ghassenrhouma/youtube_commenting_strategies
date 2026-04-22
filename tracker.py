import os
from datetime import datetime, timezone
import gspread
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH", "service_account.json")

# Sheet columns: timestamp | strategy | account | video_id | video_link | role | comment_id

_STRATEGY_LABELS = {
    "s1": "Thread Building",
    "s2": "Depth Escalation",
    "s3": "Staged Disagreement",
    "s4": "Replayable Comment",
}

_ACCOUNT_LABELS = {
    "account1": "Seif Masmoudi",
    "account2": "Amir Driri",
    "account3": "Clement Bonnefoi",
}


def get_seen_video_ids(account: str = None) -> set:
    try:
        client = gspread.service_account(filename=SERVICE_ACCOUNT_PATH)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        rows = sheet.get_all_values()
        result = set()
        for row in rows[1:]:
            if len(row) > 3 and row[3]:
                if account is None or (len(row) > 2 and row[2] == _ACCOUNT_LABELS.get(account, account)):
                    result.add(row[3])
        print(f"[TRACKER] Loaded {len(result)} seen video IDs")
        return result
    except Exception as e:
        print(f"[TRACKER] ERROR loading sheet: {e}")
        return set()


def log_action(
    strategy: str,
    account: str,
    video_id: str,
    video_title: str,
    role: str,
    replied_to_comment: str,
    text: str,
    comment_id: str,
    status: str,
    flagged: str = "no",
    dry_run: bool = False,
):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    strategy_label = _STRATEGY_LABELS.get(strategy, strategy)
    account_label = _ACCOUNT_LABELS.get(account, account)
    video_link = f"https://www.youtube.com/watch?v={video_id}"

    if dry_run:
        print("[DRY RUN] Would log row:")
        print(f"  timestamp  : {timestamp}")
        print(f"  strategy   : {strategy_label}")
        print(f"  account    : {account_label}")
        print(f"  video_id   : {video_id}")
        print(f"  video_link : {video_link}")
        print(f"  role       : {role}")
        print(f"  comment_id : {comment_id}")
        return

    client = gspread.service_account(filename=SERVICE_ACCOUNT_PATH)
    sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
    sheet.append_row([
        timestamp, strategy_label, account_label, video_id, video_link, role, comment_id,
    ])
