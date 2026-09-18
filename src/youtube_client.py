"""Heuristic YouTube 'free with ads' movie search.

The YouTube Data API does not expose a "free with ads" flag anywhere —
that's internal YouTube Movies metadata with no public API equivalent. So
this can only ever be a heuristic: search for the title, keep results from
a curated allowlist of official studio/distributor channels (configured in
config/youtube_channels.json), and let the caller label any match as
unverified. It is never treated as a confirmed result.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests

from .models import YouTubeMatch

YOUTUBE_BASE = "https://www.googleapis.com/youtube/v3"


def load_allowed_channels(path: str) -> List[dict]:
    """Loads the curated channel allowlist. Entries with an empty
    channel_id are skipped — see config/youtube_channels.json and the
    README for how to fill them in."""
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return [c for c in data.get("channels", []) if c.get("channel_id")]


class YouTubeClient:
    def __init__(self, session: requests.Session, api_key: str, allowed_channels: List[dict]):
        self.session = session
        self.api_key = api_key
        self.allowed_channel_ids = {c["channel_id"] for c in allowed_channels}
        self.channel_names_by_id = {c["channel_id"]: c["name"] for c in allowed_channels}
        self.quota_exceeded = False

    def search_free_movie(self, title: str, year: Optional[int]) -> Optional[YouTubeMatch]:
        if self.quota_exceeded or not self.allowed_channel_ids:
            return None

        # search.list only accepts a single channelId filter, and checking
        # every allowlisted channel separately would multiply quota cost
        # per title. Instead, search broadly once and filter the results
        # against the allowlist client-side.
        params = {
            "key": self.api_key,
            "part": "snippet",
            "q": f"{title} full movie",
            "type": "video",
            "videoDuration": "long",
            "maxResults": 10,
        }
        try:
            response = self.session.get(f"{YOUTUBE_BASE}/search", params=params, timeout=30)
        except requests.RequestException as exc:
            print(f"[youtube_client] request failed for {title!r}: {exc}")
            return None

        if response.status_code == 403 and "quota" in response.text.lower():
            self.quota_exceeded = True
            print(
                "[youtube_client] YouTube API quota exceeded; skipping "
                "remaining YouTube lookups for this run."
            )
            return None
        if response.status_code != 200:
            print(f"[youtube_client] unexpected HTTP {response.status_code} for {title!r}")
            return None

        for item in response.json().get("items", []):
            channel_id = item.get("snippet", {}).get("channelId")
            if channel_id in self.allowed_channel_ids:
                video_id = item.get("id", {}).get("videoId")
                if not video_id:
                    continue
                return YouTubeMatch(
                    video_title=item["snippet"]["title"],
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    channel_name=self.channel_names_by_id.get(channel_id, "Unknown"),
                )
        return None
