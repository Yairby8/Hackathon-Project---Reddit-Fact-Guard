"""
Lightweight author history fetcher using PullPush API.
Fetches recent posts/comments for a Reddit user to assess their credibility.
"""

import time
import requests

HEADERS = {
    "User-Agent": "reddit-factguard/1.0 (hackathon project)"
}

PULLPUSH_BASE = "https://api.pullpush.io/reddit/search"


def fetch_user_history(username: str, limit: int = 50) -> dict:
    """
    Fetch a user's recent comments and posts from PullPush.

    Returns:
        {
            "comments": [...],
            "posts": [...],
            "account_age_indicator": str,
            "total_items": int,
        }
    """
    if not username or username in ("[deleted]", "AutoModerator"):
        return {"comments": [], "posts": [], "account_age_indicator": "unknown", "total_items": 0}

    comments = _fetch_listing(username, "comment", limit=limit)
    posts = _fetch_listing(username, "submission", limit=limit)

    # Estimate account age from oldest item
    all_timestamps = [
        item.get("created_utc", 0)
        for item in comments + posts
        if item.get("created_utc")
    ]

    if all_timestamps:
        oldest = min(all_timestamps)
        age_days = (time.time() - oldest) / 86400
        if age_days < 7:
            age_indicator = "very_new"
        elif age_days < 30:
            age_indicator = "new"
        elif age_days < 365:
            age_indicator = "established"
        else:
            age_indicator = "veteran"
    else:
        age_indicator = "unknown"

    return {
        "comments": comments,
        "posts": posts,
        "account_age_indicator": age_indicator,
        "total_items": len(comments) + len(posts),
    }


def _fetch_listing(username: str, kind: str, limit: int = 50) -> list:
    """Fetch comments or submissions from PullPush."""
    url = f"{PULLPUSH_BASE}/{kind}/"
    params = {
        "author": username,
        "size": min(limit, 100),
        "sort": "desc",
        "sort_type": "created_utc",
    }

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"[History] PullPush returned {resp.status_code} for {username}/{kind}")
            return []

        data = resp.json()
        children = data.get("data", [])

        items = []
        for d in children:
            if kind == "comment":
                items.append({
                    "type": "comment",
                    "subreddit": d.get("subreddit", ""),
                    "created_utc": d.get("created_utc", 0),
                    "score": d.get("score", 0),
                    "body": (d.get("body", "") or "")[:300],
                })
            else:
                items.append({
                    "type": "post",
                    "subreddit": d.get("subreddit", ""),
                    "created_utc": d.get("created_utc", 0),
                    "score": d.get("score", 0),
                    "title": d.get("title", ""),
                    "body": (d.get("selftext", "") or "")[:300],
                })

        return items

    except Exception as e:
        print(f"[History] Error fetching {username}/{kind}: {e}")
        return []
