#!/usr/bin/env python3
"""
Bluesky Posts Deleter
---------------------------------------------
Deletes posts from your Bluesky account that were posted
within a date range
Requires an App Password (NOT your real password).

Setup:
  Install python

  open cmd - install request with

  pip install requests

run from cmd - execute the py file with python using the path where the script is located:
  python bskydeleter.py
"""

import requests
import time
from datetime import datetime, timezone, timedelta

# How to set up an App Password

# log in , go to settings, go to privacy, go to app password, add password, enter some name and copy the app password that will be displayed afterwards

HANDLE = "yourHandleWithoutThe@.bsky.social"  # Your Bluesky handle
APP_PASSWORD = "xxxx-xxxx-xxxx-xxxx"  # App Password from Settings → App Passwords

DRY_RUN = True  # Set to False to actually delete.
DELAY_SEC = 0.2  # Pause between deletions

DAYS_NEWEST = 1  # from date   yesterday   (1 day ago)
DAYS_OLDEST = 3  # to date     3 days ago

BASE_URL = "https://bsky.social"


def login(handle: str, app_password: str) -> tuple[str, str]:
    """Authenticate and return (access_token, did)."""
    resp = requests.post(
        f"{BASE_URL}/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": app_password},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["accessJwt"], data["did"]


def in_date_range(record: dict) -> bool:
    created_at = record.get("value", {}).get("createdAt", "")
    if not created_at:
        return False
    try:
        post_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=DAYS_OLDEST)  # 4 days ago
    window_end = now - timedelta(days=DAYS_NEWEST)  # 1 day ago
    return window_start <= post_time <= window_end


def get_all_posts(token: str, did: str) -> list[dict]:
    """Fetch every post record from the user's repository."""
    posts = []
    cursor = None
    headers = {"Authorization": f"Bearer {token}"}

    print("Fetching all posts from your repository...")
    while True:
        params = {
            "repo": did,
            "collection": "app.bsky.feed.post",
            "limit": 100,
        }
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(
            f"{BASE_URL}/xrpc/com.atproto.repo.listRecords",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

        records = data.get("records", [])
        posts.extend(records)
        print(f"  Fetched {len(posts)} posts so far...")

        cursor = data.get("cursor")

        if not cursor or not records:
            break

        # we only need posts that are newer then the start range
        created_at = records[0].get("value", {}).get("createdAt", "")
        try:
            post_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=DAYS_OLDEST)

        if post_time < window_start:
            break
        # we only need posts that are newer then the start range
    return posts


def delete_post(token: str, did: str, rkey: str) -> None:
    """Delete a single post by its rkey."""
    resp = requests.post(
        f"{BASE_URL}/xrpc/com.atproto.repo.deleteRecord",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "repo": did,
            "collection": "app.bsky.feed.post",
            "rkey": rkey,
        },
    )
    resp.raise_for_status()


def main():
    print("=" * 40)
    print("  Bluesky Post Deleter - SilverValkyrie @magicalsatori - hit me up if you have questions")
    print("=" * 40)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=DAYS_OLDEST)
    window_end = now - timedelta(days=DAYS_NEWEST)
    print(f"\nThe following time window is targeted")
    print(
        f"\nDate window: {window_start.strftime('%Y-%m-%d %H:%M UTC')}  ->  {window_end.strftime('%Y-%m-%d %H:%M UTC')}")

    if DRY_RUN:
        print("\n DRY RUN MODE - no posts will actually be deleted")
        print("   Set DRY_RUN = False in the script to actually delete\n")

    # Authenticate
    print(f"Logging in as {HANDLE}...")
    try:
        token, did = login(HANDLE, APP_PASSWORD)
    except requests.HTTPError as e:
        print(f"\n Login failed: {e.response.text}")
        return
    print(f"Logged in! {did}\n")

    all_posts = get_all_posts(token, did)
    print(f"\nPosts found: {len(all_posts)}")

    posts_in_range = [
        p for p in all_posts
        if in_date_range(p)
    ]

    print(f"Posts posts found to be deleted: {len(posts_in_range)}")

    if not posts_in_range:
        print("\nNothing found, check the date")
        return

    # Show a sample
    print(f"\nPosts to be deleted:")
    for r in posts_in_range[:10]:
        created = r["value"].get("createdAt", "unknown date")
        text = r["value"].get("text", "")[:70]
        print(f"  [{created[:10]}] {text!r}")
    if len(posts_in_range) > 5:
        print(f"  ... {len(posts_in_range) - 10} more.")

    if DRY_RUN:
        print(f"\n[DRY RUN] Would delete {len(posts_in_range)} posts.")
        print("Set DRY_RUN = False and re-run to actually delete them.")
        return

    # Confirm before deleting
    confirm = input(f"\nAbout to permanently delete {len(posts_in_range)} posts. Type YES to confirm: ")
    if confirm.strip() != "YES":
        print("Aborted.")
        return

    # Delete
    deleted = 0
    failed = 0
    print("\nDeleting...")
    for record in posts_in_range:
        rkey = record["uri"].split("/")[-1]
        try:
            delete_post(token, did, rkey)
            deleted += 1
            if deleted % 10 == 0:
                print(f"  Deleted {deleted}/{len(posts_in_range)}...")
            time.sleep(DELAY_SEC)
        except requests.HTTPError as e:
            print(f"  Failed to delete {rkey}: {e.response.text}")
            failed += 1

    print(f"\nDone! Deleted {deleted} posts. Failed: {failed}")


if __name__ == "__main__":
    main()
