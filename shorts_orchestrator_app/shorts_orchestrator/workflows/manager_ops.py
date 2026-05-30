from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from shorts_orchestrator.agents.router import run_agent
from shorts_orchestrator.settings import (
    BRAND_BIBLES_DIR,
    CONFIG_DIR,
    DATA_DIR,
    DB_DIR,
    INPUTS_DIR,
    LEARNING_DIR,
    LOGS_DIR,
    OUTPUTS_DIR,
    PROMPT_VERSIONS_DIR,
    QUEUE_DIR,
    VOICEOVER_DIR,
    accounts_config,
    load_yaml,
    models_config,
    schedule_config,
    settings,
)
from shorts_orchestrator.storage.db import (
    connect,
    list_recent_runs,
    list_recent_videos,
    save_manager_report,
)
from shorts_orchestrator.workflows.analytics_loop import update_channel_learning

MANAGER_REPORTS_DIR = LOGS_DIR / "manager_reports"
MANAGER_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_PACKET_KEYS = {
    "topic",
    "target_account",
    "video_prompt",
    "negative_prompt",
    "metadata",
    "gates",
}

SAFE_REQUIRED_DIRS = [
    DATA_DIR,
    INPUTS_DIR,
    OUTPUTS_DIR,
    LOGS_DIR,
    DB_DIR,
    BRAND_BIBLES_DIR,
    PROMPT_VERSIONS_DIR,
    LEARNING_DIR,
    VOICEOVER_DIR,
    QUEUE_DIR,
    MANAGER_REPORTS_DIR,
]


class ManagerFinding(dict):
    """Small dict subclass for clearer type intent."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_safe(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {"_parse_error": True, "raw_preview": value[:500]}


def _run_cmd(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, out
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Timed out running: {' '.join(cmd)}"
    except Exception as exc:
        return False, f"Error running {' '.join(cmd)}: {exc}"


def _ollama_tags(timeout: int = 5) -> dict[str, Any]:
    url = settings.ollama_host.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc), "url": url}


def _configured_ollama_models() -> set[str]:
    models: set[str] = set()
    for cfg in (models_config.get("models") or {}).values():
        name = str(cfg.get("provider_model", ""))
        if name.startswith("ollama/"):
            models.add(name.split("ollama/", 1)[1])
    return models


def _installed_ollama_models() -> set[str]:
    tags = _ollama_tags()
    if tags.get("error"):
        return set()
    found: set[str] = set()
    for item in tags.get("models", []) or []:
        name = item.get("name") or item.get("model")
        if name:
            found.add(str(name))
            # qwen2.5:7b and qwen2.5:7b-instruct style comparison support.
            found.add(str(name).split("@", 1)[0])
    return found


def _status(level: str, code: str, message: str, fix: str | None = None, data: dict[str, Any] | None = None) -> ManagerFinding:
    return ManagerFinding({"level": level, "code": code, "message": message, "fix": fix, "data": data or {}})


def validate_prompt_packets(limit: int = 25) -> list[ManagerFinding]:
    findings: list[ManagerFinding] = []
    packet_files = sorted(OUTPUTS_DIR.glob("*_ai_prompt_packet_*.json"), reverse=True)[:limit]
    for path in packet_files:
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            findings.append(_status("error", "packet_parse", f"Cannot parse prompt packet {path.name}: {exc}", "Regenerate this packet or remove it from the queue."))
            continue
        missing = REQUIRED_PACKET_KEYS - set(packet.keys())
        if missing:
            findings.append(_status("warning", "packet_missing_keys", f"Prompt packet {path.name} is missing keys: {sorted(missing)}", "Regenerate or patch this packet before using it."))
        metadata = packet.get("metadata") or {}
        if metadata.get("privacy_status") != "private":
            findings.append(_status("warning", "packet_not_private", f"Prompt packet {path.name} is not set to private upload.", "Set metadata.privacy_status to private before upload."))
        gates = packet.get("gates") or {}
        for gate_name, gate in gates.items():
            if isinstance(gate, dict) and str(gate.get("status", "")).upper() == "REJECT":
                findings.append(_status("warning", "packet_rejected_gate", f"Prompt packet {path.name} has rejected gate: {gate_name}.", "Do not generate or upload without manual revision.", {"gate": gate}))
    if not packet_files:
        findings.append(_status("info", "no_packets", "No AI prompt packets found yet.", "Run ai-packet or ai-chain to create production candidates."))
    return findings


def manager_health_check(repair: bool = False, smoke_test: bool = False, packet_limit: int = 25) -> dict[str, Any]:
    findings: list[ManagerFinding] = []
    repairs: list[str] = []

    # Safe filesystem repairs.
    for path in SAFE_REQUIRED_DIRS:
        if not path.exists():
            findings.append(_status("warning", "missing_dir", f"Missing directory: {path}", "Create the directory."))
            if repair:
                path.mkdir(parents=True, exist_ok=True)
                repairs.append(f"Created directory: {path}")

    # Config checks.
    required_config = ["accounts.yaml", "models.yaml", "policy_rules.yaml", "posting_schedule.yaml", "voiceover.yaml"]
    for name in required_config:
        path = CONFIG_DIR / name
        if not path.exists():
            findings.append(_status("error", "missing_config", f"Missing config file: {name}", "Restore the file from the app ZIP or recreate it."))

    accounts = accounts_config.get("accounts") or {}
    if not accounts:
        findings.append(_status("error", "no_accounts", "No channels/accounts are configured.", "Add channels to config/accounts.yaml."))

    for key, acct in accounts.items():
        bible = BRAND_BIBLES_DIR / f"{key}.brand_bible.yaml"
        if not bible.exists():
            findings.append(_status("warning", "missing_brand_bible", f"Missing brand bible for {key}.", "Create a channel brand bible before generating daily videos."))
            if repair:
                skeleton = {
                    "channel": key,
                    "voice": acct.get("brand_voice", "original, clear, safe"),
                    "niche": acct.get("niche", ""),
                    "format_rules": {"target_length_seconds": "18-35", "upload_privacy": "private"},
                    "banned_styles": ["celebrity likeness", "copyrighted characters", "real-person cloning", "reused clips"],
                    "learning_notes": [],
                }
                bible.write_text(yaml.safe_dump(skeleton, sort_keys=False), encoding="utf-8")
                repairs.append(f"Created brand bible skeleton: {bible.name}")

    if settings.default_upload_privacy != "private":
        findings.append(_status("warning", "unsafe_default_privacy", f"DEFAULT_UPLOAD_PRIVACY is {settings.default_upload_privacy!r}, not private.", "Use private by default and publish manually after review."))

    sched_default = (schedule_config.get("posting_schedule") or {}).get("default", {}) if isinstance(schedule_config, dict) else {}
    if str(sched_default.get("publish_mode", "manual_review")) != "manual_review":
        findings.append(_status("warning", "publish_mode_not_manual", "Default publish_mode is not manual_review.", "Keep generated channels in manual_review mode until channel health is proven."))

    # Tool checks.
    if not shutil.which("ffmpeg"):
        findings.append(_status("warning", "ffmpeg_missing", "FFmpeg was not found in PATH.", "Install FFmpeg and add it to PATH before rendering videos."))
    if not shutil.which("ollama"):
        findings.append(_status("warning", "ollama_missing", "Ollama CLI was not found in PATH.", "Install Ollama if using local models."))
    else:
        ok, out = _run_cmd(["ollama", "--version"], timeout=5)
        findings.append(_status("info" if ok else "warning", "ollama_version", f"Ollama version check: {out[:200] or 'no output'}"))

    tags = _ollama_tags()
    if tags.get("error"):
        findings.append(_status("warning", "ollama_api_unavailable", f"Ollama API unavailable at {tags.get('url')}: {tags.get('error')}", "Start Ollama before running local AI agents."))
    else:
        installed = _installed_ollama_models()
        configured = _configured_ollama_models()
        missing = sorted(m for m in configured if m not in installed)
        if missing:
            findings.append(_status("warning", "ollama_models_missing", f"Configured Ollama models not found locally: {missing}", "Run ollama pull for each missing model.", {"missing": missing}))
        else:
            findings.append(_status("info", "ollama_models_ok", "Configured Ollama models appear to be installed."))

    # DB check.
    try:
        with connect() as conn:
            conn.execute("SELECT 1").fetchone()
        findings.append(_status("info", "db_ok", f"SQLite database is available at {DB_DIR}."))
    except sqlite3.Error as exc:
        findings.append(_status("error", "db_error", f"SQLite database error: {exc}", "Back up data/db and recreate the database if needed."))

    findings.extend(validate_prompt_packets(packet_limit))

    # Recent run checks.
    recent_runs = list_recent_runs(30)
    workflow_counts = Counter(r.get("workflow", "unknown") for r in recent_runs)
    parse_errors = 0
    blocked = 0
    for run in recent_runs:
        payload = _read_json_safe(run.get("payload_json"))
        if payload.get("_parse_error"):
            parse_errors += 1
        gen = payload.get("generation_result") or {}
        if isinstance(gen, dict) and gen.get("status") == "blocked_by_pre_generation_gate":
            blocked += 1
    if parse_errors:
        findings.append(_status("warning", "run_payload_parse_errors", f"{parse_errors} recent run payloads could not be parsed.", "Review those rows in the runs table."))
    if blocked:
        findings.append(_status("info", "blocked_generations", f"{blocked} recent generations were blocked by safety/quality gates.", "This is usually good; review whether the prompts need a safer format."))

    if smoke_test:
        try:
            smoke = run_agent(
                "manager",
                "Reply with exactly: MANAGER_SMOKE_TEST_OK",
                context="Health check smoke test. No external actions.",
                max_tokens=50,
            )
            findings.append(_status("info" if "MANAGER_SMOKE_TEST_OK" in smoke else "warning", "agent_smoke_test", f"Manager agent smoke test response: {smoke[:200]}"))
        except Exception as exc:
            findings.append(_status("error", "agent_smoke_test_failed", f"Manager agent smoke test failed: {exc}", "Check LiteLLM, Ollama, API keys, and configured model names."))

    level_order = {"error": 3, "warning": 2, "info": 1}
    worst = max((level_order.get(f["level"], 0) for f in findings), default=0)
    status = "ERROR" if worst >= 3 else "WARNING" if worst == 2 else "OK"
    return {
        "created_at": _utc_now(),
        "status": status,
        "repair_mode": repair,
        "repairs_applied": repairs,
        "workflow_counts_recent": dict(workflow_counts),
        "recent_runs_checked": len(recent_runs),
        "findings": findings,
    }


def model_upgrade_scan() -> dict[str, Any]:
    installed = sorted(_installed_ollama_models())
    configured = sorted(_configured_ollama_models())
    missing = sorted(m for m in configured if m not in installed)
    unused = sorted(m for m in installed if m not in configured)
    watchlist_path = CONFIG_DIR / "model_upgrade_watchlist.yaml"
    watchlist = load_yaml(watchlist_path)
    recommendations = []
    if missing:
        recommendations.append("Pull missing configured models before running automated batches.")
    if unused:
        recommendations.append("Review unused local models; they may be candidates for testing or cleanup.")
    recommendations.append("Do not silently switch production agents to new models. Run A/B tests on private candidates first.")
    recommendations.append("Use stronger paid models only for compliance/critic/final QA after a channel shows traction.")
    return {
        "created_at": _utc_now(),
        "configured_ollama_models": configured,
        "installed_ollama_models": installed,
        "missing_configured_models": missing,
        "unused_installed_models": unused,
        "watchlist_path": str(watchlist_path),
        "watchlist": watchlist,
        "recommendations": recommendations,
    }


def _aggregate_recent_local_numbers(account: str | None = None, days: int = 1) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    runs = list_recent_runs(200)
    videos = list_recent_videos(200)
    filtered_runs = []
    filtered_videos = []
    for r in runs:
        try:
            created = datetime.fromisoformat(r["created_at"])
        except Exception:
            created = datetime.now(timezone.utc)
        if created >= cutoff and (account is None or r.get("account") == account):
            filtered_runs.append(r)
    for v in videos:
        try:
            created = datetime.fromisoformat(v["created_at"])
        except Exception:
            created = datetime.now(timezone.utc)
        if created >= cutoff and (account is None or v.get("account") == account):
            filtered_videos.append(v)
    by_workflow = Counter(r.get("workflow", "unknown") for r in filtered_runs)
    by_account = Counter(v.get("account", "unknown") for v in filtered_videos)
    privacy_counts = Counter(v.get("privacy_status", "unknown") for v in filtered_videos)
    return {
        "days": days,
        "account_filter": account,
        "runs": len(filtered_runs),
        "videos_logged": len(filtered_videos),
        "runs_by_workflow": dict(by_workflow),
        "videos_by_account": dict(by_account),
        "videos_by_privacy": dict(privacy_counts),
    }


def _revenue_config_for(account: str) -> dict[str, float]:
    cfg = load_yaml(CONFIG_DIR / "revenue_tracking.yaml").get("revenue_tracking", {})
    base = cfg.get("default", {}) or {}
    acct = (cfg.get("accounts", {}) or {}).get(account, {}) or {}
    merged = {**base, **acct}
    return {
        "rpm_estimate_usd": float(merged.get("rpm_estimate_usd", 0.0) or 0.0),
        "estimated_variable_cost_per_video_usd": float(merged.get("estimated_variable_cost_per_video_usd", 0.0) or 0.0),
        "estimated_daily_fixed_cost_usd": float(merged.get("estimated_daily_fixed_cost_usd", 0.0) or 0.0),
    }


def _estimate_profit(account: str, totals: dict[str, float], days: int | None = None) -> dict[str, Any]:
    rcfg = _revenue_config_for(account)
    views = float(totals.get("views", 0.0) or 0.0)
    # If YouTube Analytics later exposes estimatedRevenue in the result, prefer it.
    revenue = float(totals.get("estimatedRevenue", 0.0) or 0.0)
    source = "youtube_analytics_estimatedRevenue" if revenue else "rpm_estimate_config"
    if not revenue:
        revenue = (views / 1000.0) * rcfg["rpm_estimate_usd"]
    local_nums = _aggregate_recent_local_numbers(account, days=days or 1)
    video_count = int(local_nums.get("videos_logged", 0) or 0)
    costs = (video_count * rcfg["estimated_variable_cost_per_video_usd"]) + rcfg["estimated_daily_fixed_cost_usd"]
    return {
        "revenue_source": source,
        "views": views,
        "revenue_usd": round(revenue, 4),
        "estimated_costs_usd": round(costs, 4),
        "estimated_profit_usd": round(revenue - costs, 4),
        "config": rcfg,
        "note": "This is an estimate unless YouTube Analytics estimatedRevenue is available and your channel is monetized.",
    }


def _analytics_brief(account: str, start: str | None, end: str | None, pull_analytics: bool) -> dict[str, Any]:
    if not pull_analytics:
        return {"status": "skipped", "note": "Run with --pull-analytics to update view/subscriber/profit numbers from YouTube."}
    try:
        result = update_channel_learning(account, start, end)
        rows = result.get("analytics", {}).get("rows", []) or []
        totals = defaultdict(float)
        headers = result.get("analytics", {}).get("columnHeaders", []) or []
        names = [h.get("name") for h in headers]
        for row in rows:
            for idx, name in enumerate(names):
                if idx == 0 or name == "day":
                    continue
                try:
                    totals[name] += float(row[idx])
                except Exception:
                    pass
        totals_dict = dict(totals)
        profit = _estimate_profit(account, totals_dict)
        return {"status": "updated", "snapshot_id": result.get("snapshot_id"), "totals": totals_dict, "profit_estimate": profit, "lessons": result.get("lessons"), "notes_path": result.get("notes_path")}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "note": "Analytics requires YouTube OAuth and may not expose revenue until the channel is monetized."}


def daily_debrief(account: str | None = None, start: str | None = None, end: str | None = None,
                  pull_analytics: bool = False, days: int = 1) -> dict[str, Any]:
    accounts = accounts_config.get("accounts") or {}
    target_accounts = [account] if account else list(accounts.keys())
    health = manager_health_check(repair=False, smoke_test=False, packet_limit=15)
    local_numbers = _aggregate_recent_local_numbers(account, days=days)
    analytics = {acct: _analytics_brief(acct, start, end, pull_analytics) for acct in target_accounts}
    upgrade = model_upgrade_scan()

    context = {
        "account": account or "all",
        "local_numbers": local_numbers,
        "health_status": health.get("status"),
        "health_findings": health.get("findings", [])[:20],
        "analytics": analytics,
        "model_upgrade_scan": {
            "missing_configured_models": upgrade.get("missing_configured_models"),
            "unused_installed_models": upgrade.get("unused_installed_models"),
            "recommendations": upgrade.get("recommendations"),
        },
        "posting_policy": "Private upload by default. Public publishing requires review unless explicitly changed by the user.",
    }
    try:
        narrative = run_agent(
            "ops_manager",
            "Create a daily operations debrief for this YouTube Shorts AI studio. Include: system status, what ran, blockers, analytics/view/subscriber notes, monetization/revenue note if available, model/update recommendations, and next actions. Be concise and operational. Do not promise guaranteed monetization.",
            context=json.dumps(context, ensure_ascii=False, indent=2),
            max_tokens=1800,
        )
    except Exception as exc:
        narrative = (
            f"# Daily Operations Debrief\n\n"
            f"Manager LLM summary failed: {exc}\n\n"
            f"Health status: {health.get('status')}\n\n"
            f"Local numbers: {json.dumps(local_numbers, indent=2)}\n\n"
            f"Analytics: {json.dumps(analytics, indent=2)}\n"
        )

    report_date = date.today().isoformat()
    suffix = account or "all_channels"
    report_path = MANAGER_REPORTS_DIR / f"{report_date}_{suffix}_debrief.md"
    report = f"# Shorts Orchestrator Daily Debrief — {report_date}\n\n{narrative}\n\n---\n\n## Raw Manager Context\n\n```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```\n"
    report_path.write_text(report, encoding="utf-8")
    report_id = save_manager_report(account or "all", "daily_debrief", report, context)
    return {"report_id": report_id, "report_path": str(report_path), "report": report, "context": context}


def manager_supervise(account: str | None = None, repair: bool = False, pull_analytics: bool = False,
                      smoke_test: bool = False, days: int = 1) -> dict[str, Any]:
    health = manager_health_check(repair=repair, smoke_test=smoke_test, packet_limit=25)
    debrief = daily_debrief(account=account, pull_analytics=pull_analytics, days=days)
    upgrade = model_upgrade_scan()
    payload = {
        "created_at": _utc_now(),
        "health": health,
        "debrief_path": debrief.get("report_path"),
        "upgrade_scan": upgrade,
        "manager_policy": {
            "safe_repairs_allowed": ["create missing directories", "create missing brand bible skeletons", "write reports"],
            "requires_manual_approval": ["public publish", "model switch", "model pull/update", "supplier/payment actions", "deleting files"],
        },
    }
    save_manager_report(account or "all", "supervise", json.dumps(payload, ensure_ascii=False, indent=2), payload)
    return payload
