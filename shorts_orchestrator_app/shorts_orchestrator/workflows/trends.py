from __future__ import annotations

import json
from typing import Any

from shorts_orchestrator.agents.router import run_agent
from shorts_orchestrator.connectors.youtube_client import search_youtube
from shorts_orchestrator.storage.db import save_run


def scan_youtube_trends(account: str, query: str, max_results: int = 10, creative_commons_only: bool = False) -> dict[str, Any]:
    license_filter = "creativeCommon" if creative_commons_only else None
    items = search_youtube(query=query, max_results=max_results, order="viewCount", video_license=license_filter)
    simplified = []
    for item in items:
        vid = item.get("id", {}).get("videoId")
        snip = item.get("snippet", {})
        simplified.append({
            "video_id": vid,
            "title": snip.get("title"),
            "channel": snip.get("channelTitle"),
            "published_at": snip.get("publishedAt"),
            "description": (snip.get("description") or "")[:400],
        })

    analysis = run_agent(
        "trend_scout",
        "Analyze these YouTube search results for reusable trend patterns. Do not suggest copying the videos. Extract ethical/original content angles, hook patterns, title formulas, and risks.",
        context=json.dumps(simplified, ensure_ascii=False, indent=2),
        max_tokens=1800,
    )
    payload = {"query": query, "creative_commons_only": creative_commons_only, "items": simplified, "analysis": analysis}
    payload["run_id"] = save_run(account, "scan_youtube_trends", query, payload)
    return payload
