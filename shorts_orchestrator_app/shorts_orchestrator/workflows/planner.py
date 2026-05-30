from __future__ import annotations

import json
from typing import Any

from shorts_orchestrator.agents.router import run_agent, run_panel
from shorts_orchestrator.settings import accounts_config, policy_config
from shorts_orchestrator.storage.db import save_run


def get_account(account: str) -> dict[str, Any]:
    accounts = accounts_config.get("accounts", {})
    if account not in accounts:
        raise KeyError(f"Unknown account '{account}'. Add it to config/accounts.yaml")
    return accounts[account]


def plan_short(account: str, topic: str, source_notes: str | None = None) -> dict[str, Any]:
    acct = get_account(account)
    shared = json.dumps({
        "account": account,
        "account_config": acct,
        "policy_rules": policy_config,
        "topic": topic,
        "source_notes": source_notes or "No source notes provided. Use original or authorized footage only.",
    }, ensure_ascii=False, indent=2)

    tasks = {
        "trend_scout": (
            "Identify 5 Shorts angles for this account/topic. Include hook, audience intent, "
            "why it could work, and risk level. Do not suggest unlicensed reposts."
        ),
        "scriptwriter": (
            "Write one 20-40 second original script for the best angle. Include on-screen text, "
            "voiceover, and a punchy ending."
        ),
        "editor": (
            "Create an edit plan for a vertical YouTube Short using local/original/authorized footage. "
            "Include shot list, pacing, captions, B-roll notes, and ideal length."
        ),
        "compliance": (
            "Review the planned Short for YouTube monetization, reused content, AI disclosure, copyright, "
            "kids-content, and advertiser suitability risk. Return PASS, REVIEW, or REJECT with fixes."
        ),
        "critic": (
            "Find flaws in the plan and propose specific improvements that increase originality, retention, "
            "and policy safety."
        ),
    }
    outputs = run_panel(tasks, shared_context=shared)
    final = run_agent(
        "manager",
        "Create the final production brief. Include: concept, script, edit plan, title ideas, description, tags, compliance status, and next actions.",
        context=json.dumps(outputs, ensure_ascii=False, indent=2),
        max_tokens=2000,
    )
    payload = {"agents": outputs, "final": final}
    run_id = save_run(account, "plan_short", topic, payload)
    payload["run_id"] = run_id
    return payload


def compliance_review(account: str, title: str, description: str, source_rights: str, script: str | None = None) -> dict[str, Any]:
    acct = get_account(account)
    context = json.dumps({
        "account": account,
        "account_config": acct,
        "policy_rules": policy_config,
        "title": title,
        "description": description,
        "source_rights": source_rights,
        "script": script or "",
    }, ensure_ascii=False, indent=2)
    review = run_agent(
        "compliance",
        "Return a conservative YouTube risk review with status PASS, REVIEW, or REJECT. Include specific fixes before upload.",
        context=context,
        max_tokens=1200,
    )
    payload = {"review": review}
    run_id = save_run(account, "compliance_review", title, payload)
    payload["run_id"] = run_id
    return payload
