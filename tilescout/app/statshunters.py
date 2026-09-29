"""
StatsHunters Client Integration with full pagination and local disk caching.
Fetches user activity polylines and visited z14 tile coordinates across all activities.
"""

import os
import re
import json
import requests
from typing import Set, Tuple, Dict, Any

STATSHUNTERS_BASE = "https://statshunters.com"
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")

class StatsHuntersClient:
    def __init__(self, share_code_or_url: str):
        clean_code = share_code_or_url.strip().rstrip("/")
        if "/" in clean_code:
            clean_code = clean_code.split("/")[-1]
        self.share_code = clean_code
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*"
        })
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.cache_file = os.path.join(CACHE_DIR, f"{self.share_code}_tiles.json")

    def fetch_tiles_and_activities(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieves all visited z14 tiles and activities across all paginated pages.
        Caches results locally for quick repeated lookups.
        """
        if not force_refresh and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    cached = json.load(f)
                    tiles_set = set(tuple(t) for t in cached.get("tiles", []))
                    return {
                        "share_code": self.share_code,
                        "total_activities": cached.get("total_activities", 0),
                        "visited_tiles_count": len(tiles_set),
                        "tiles": tiles_set,
                        "cached": True
                    }
            except Exception:
                pass

        share_page_url = f"{STATSHUNTERS_BASE}/share/{self.share_code}"
        resp = self.session.get(share_page_url, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to access StatsHunters share page ({resp.status_code})")

        token_match = re.search(r'\"csrfToken\":\"([^\"]+)\"', resp.text)
        if not token_match:
            raise RuntimeError("Could not parse CSRF token from StatsHunters page")

        csrf_token = token_match.group(1)
        api_headers = {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-TOKEN": csrf_token,
        }

        all_tiles: Set[Tuple[int, int]] = set()
        page = 1
        total_activities = 0

        while True:
            api_url = f"{STATSHUNTERS_BASE}/share/{self.share_code}/api/activities?page={page}"
            act_resp = self.session.get(api_url, headers=api_headers, timeout=25)
            if act_resp.status_code != 200:
                break

            payload = act_resp.json()
            activities = payload.get("activities", [])
            if not activities:
                break

            total_activities += len(activities)
            for act in activities:
                for t in act.get("tiles", []):
                    all_tiles.add((t["x"], t["y"]))

            limit = payload.get("meta", {}).get("limit", 500)
            if len(activities) < limit:
                break
            page += 1

        # Cache to disk
        try:
            with open(self.cache_file, "w") as f:
                json.dump({
                    "total_activities": total_activities,
                    "tiles": list(all_tiles)
                }, f)
        except Exception:
            pass

        return {
            "share_code": self.share_code,
            "total_activities": total_activities,
            "visited_tiles_count": len(all_tiles),
            "tiles": all_tiles,
            "cached": False
        }
