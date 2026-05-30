from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from shorts_orchestrator.agents.router import run_agent
from shorts_orchestrator.brand import append_learning_notes, load_brand_bible
from shorts_orchestrator.connectors.youtube_client import get_channel_basic_analytics
from shorts_orchestrator.storage.db import save_analytics_snapshot


def update_channel_learning(account: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
    end_date = end or date.today().isoformat()
    start_date = start or (date.today() - timedelta(days=14)).isoformat()
    analytics = get_channel_basic_analytics(start_date, end_date)
    brand_bible = load_brand_bible(account)
    lessons = run_agent(
        "analytics_agent",
        "Analyze these YouTube analytics for a Shorts channel. Return practical lessons for future prompts: hooks, ideal length, topic/style direction, posting cadence, and what to stop doing. Do not overclaim from limited data.",
        context=json.dumps({"account": account, "brand_bible": brand_bible, "analytics": analytics}, ensure_ascii=False, indent=2),
        max_tokens=1600,
    )
    snapshot_id = save_analytics_snapshot(account, start_date, end_date, analytics, lessons)
    notes_path = append_learning_notes(account, f"# Analytics lessons {start_date} to {end_date}\n\n{lessons}")
    return {"snapshot_id": snapshot_id, "start": start_date, "end": end_date, "analytics": analytics, "lessons": lessons, "notes_path": str(notes_path)}
