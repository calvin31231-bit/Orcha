from __future__ import annotations

from typing import Any

from shorts_orchestrator.settings import schedule_config
from shorts_orchestrator.workflows.ai_pipeline import run_ai_video_chain


def _account_schedule(account: str) -> dict[str, Any]:
    cfg = schedule_config.get("posting_schedule", {}) if isinstance(schedule_config, dict) else {}
    return (cfg.get("accounts", {}) or {}).get(account, cfg.get("default", {})) or {}


def run_daily_batch(account: str, queries: list[str], generate: bool = False, provider: str = "mock",
                    workflow_path: str | None = None, wait: bool = False, use_youtube: bool = True,
                    force: bool = False, voiceover: bool = True, voice_provider: str = "mock") -> dict[str, Any]:
    sched = _account_schedule(account)
    max_private_uploads = int(sched.get("max_private_uploads_per_day", 3))
    max_public_posts = int(sched.get("max_public_posts_per_day", 1))
    max_batch = int(sched.get("max_generated_candidates_per_day", max_private_uploads))
    selected = queries[:max_batch]
    results = []
    for q in selected:
        result = run_ai_video_chain(
            account=account,
            trend_query=q,
            provider=provider,
            generate=generate,
            workflow_path=workflow_path,
            wait=wait,
            use_youtube=use_youtube,
            force=force,
            voiceover=voiceover,
            voice_provider=voice_provider,
        )
        results.append(result)
    return {
        "account": account,
        "queries_requested": queries,
        "queries_processed": selected,
        "schedule_guardrails": {
            "max_generated_candidates_per_day": max_batch,
            "max_private_uploads_per_day": max_private_uploads,
            "max_public_posts_per_day": max_public_posts,
            "recommended_public_flow": "private upload first, then manual review/schedule in YouTube Studio",
        },
        "results": results,
    }
