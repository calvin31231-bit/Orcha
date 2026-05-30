from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shorts_orchestrator.agents.router import run_agent
from shorts_orchestrator.brand import load_brand_bible, load_learning_notes
from shorts_orchestrator.media.ai_video import generate_video_from_packet, write_prompt_packet
from shorts_orchestrator.media.voiceover import generate_voiceover_from_packet
from shorts_orchestrator.settings import accounts_config, policy_config
from shorts_orchestrator.storage.db import save_run, save_video
from shorts_orchestrator.workflows.quality import (
    generation_allowed,
    originality_check,
    pre_generation_compliance_gate,
    score_idea,
    write_prompt_version_log,
)
from shorts_orchestrator.workflows.trends import scan_youtube_trends


def _accounts_summary() -> dict[str, Any]:
    return accounts_config.get("accounts", {}) or {}


def _build_shared_context(account: str, acct: dict[str, Any], accounts: dict[str, Any], trend_query: str,
                          trend_notes: str | None, trend_payload: dict[str, Any]) -> dict[str, Any]:
    brand_bible = load_brand_bible(account)
    learning_notes = load_learning_notes(account)
    return {
        "target_account": account,
        "target_account_config": acct,
        "brand_bible": brand_bible,
        "analytics_learning_notes": learning_notes,
        "all_accounts": accounts,
        "policy_rules": policy_config,
        "trend_query": trend_query,
        "trend_notes": trend_notes or "No manual trend notes supplied.",
        "trend_payload": trend_payload,
        "required_chain": [
            "AI#1 Trend Scout extracts trend patterns without copying videos.",
            "AI#2 Concept/Prompt Engineer turns patterns into an original video concept.",
            "Idea Scorer grades hook, novelty, brand fit, safety, and production effort before generation.",
            "Pre-generation Compliance Gate blocks risky concepts before GPU time is spent.",
            "Narration Director creates original voiceover and timed caption beats.",
            "AI#3 Video Generator creates a prompt packet for ComfyUI/Wan/LTX/Hunyuan or another generator.",
            "Originality Checker compares against prior channel work to avoid mass-produced repetition.",
            "AI#4 Reviewer checks monetization/TOS risk and marks PASS/REVIEW/REJECT.",
            "AI#5 Channel Router picks the best configured channel or manual_review.",
            "All uploads stay private by default until human review.",
        ],
    }


def create_ai_prompt_packet(account: str, trend_query: str, trend_notes: str | None = None,
                            max_results: int = 5, use_youtube: bool = True) -> dict[str, Any]:
    accounts = _accounts_summary()
    acct = accounts.get(account)
    if not acct:
        raise KeyError(f"Unknown account '{account}'. Add it to config/accounts.yaml")

    trend_payload: dict[str, Any] = {}
    if use_youtube:
        try:
            trend_payload = scan_youtube_trends(account=account, query=trend_query, max_results=max_results)
        except Exception as exc:
            trend_payload = {
                "query": trend_query,
                "analysis": f"YouTube trend scan unavailable: {exc}. Use trend_notes and niche context only.",
                "items": [],
            }

    shared = _build_shared_context(account, acct, accounts, trend_query, trend_notes, trend_payload)

    scout = run_agent(
        "trend_scout",
        "Extract 3-5 trend clusters and original angles. Do not copy any source video. Keep it safe for monetization and brand-specific.",
        context=json.dumps(shared, ensure_ascii=False, indent=2),
        max_tokens=1600,
    )
    concept = run_agent(
        "prompt_engineer",
        "Choose the best angle and create an original concept for an AI-generated Short. Avoid copyrighted characters, real people, celebrity likeness, fake events, cloned voices, and reused clips. Include hook, story, visual style, loop/payoff, and why it fits the channel brand bible.",
        context=json.dumps({**shared, "trend_scout_output": scout}, ensure_ascii=False, indent=2),
        max_tokens=1700,
    )

    idea_score = score_idea(account, shared, concept)
    preflight = pre_generation_compliance_gate(account, shared, concept, idea_score)

    narration = run_agent(
        "narration_director",
        "Create an original voiceover/narration plan for this Short. Return only valid JSON with keys: use_voiceover boolean, voice_style, script, timed_beats[{start,end,line,visual,sfx}], caption_lines, music_sfx_notes, ai_disclosure_note. If the channel brand usually prefers no voice, explain that and provide caption-only beats instead.",
        context=json.dumps({**shared, "trend_scout_output": scout, "concept_output": concept, "idea_score": idea_score, "preflight": preflight}, ensure_ascii=False, indent=2),
        max_tokens=1500,
    )
    try:
        narration_plan = json.loads(narration)
    except json.JSONDecodeError:
        narration_plan = {"use_voiceover": True, "voice_style": acct.get("brand_voice", "original synthetic narrator"), "script": narration, "timed_beats": [], "caption_lines": []}

    video_prompt = run_agent(
        "video_generator",
        "Create a production-ready JSON prompt packet for text-to-video. Return only valid JSON with keys: topic, target_account, video_prompt, negative_prompt, scene_plan, narration, voiceover, on_screen_text, metadata{title,description,tags,category_id,privacy_status,made_for_kids,ai_disclosure_required}, compliance_assumptions. Use 9:16, 15-40 seconds, original visuals, and no copyrighted/real-person imitation. Include the provided narration plan.",
        context=json.dumps({**shared, "trend_scout_output": scout, "concept_output": concept, "idea_score": idea_score, "preflight": preflight, "narration_plan": narration_plan}, ensure_ascii=False, indent=2),
        max_tokens=2400,
    )

    try:
        packet = json.loads(video_prompt)
    except json.JSONDecodeError:
        packet = {
            "topic": trend_query,
            "target_account": account,
            "video_prompt": video_prompt,
            "negative_prompt": "copyrighted characters, celebrity likeness, real person imitation, gore, violence, sexual content, hateful content, misleading realism, watermark, logo, low quality",
            "scene_plan": [],
            "narration": narration_plan.get("script", ""),
            "voiceover": narration_plan,
            "on_screen_text": narration_plan.get("caption_lines", []),
            "metadata": {
                "title": trend_query[:90],
                "description": "AI-generated original Short. Review before publishing.",
                "tags": [],
                "category_id": acct.get("category_id", "22"),
                "privacy_status": "private",
                "made_for_kids": bool(acct.get("made_for_kids", False)),
                "ai_disclosure_required": True,
            },
            "compliance_assumptions": ["LLM returned non-JSON; packet created as fallback."],
        }

    packet.setdefault("target_account", account)
    packet.setdefault("topic", trend_query)
    packet.setdefault("metadata", {})
    packet["metadata"]["privacy_status"] = "private"
    packet["metadata"].setdefault("made_for_kids", bool(acct.get("made_for_kids", False)))
    packet["metadata"].setdefault("ai_disclosure_required", bool(acct.get("ai_disclosure_required", True)))
    packet.setdefault("voiceover", narration_plan)
    packet["agent_outputs"] = {
        "trend_scout": scout,
        "prompt_engineer": concept,
        "narration_director": narration_plan,
    }
    packet["gates"] = {"idea_score": idea_score, "preflight_compliance": preflight}

    original_text = json.dumps({"concept": concept, "packet": packet}, ensure_ascii=False)
    originality = originality_check(account, original_text)
    packet["gates"]["originality_check"] = originality

    prompt_version_path = write_prompt_version_log(account, packet, {
        "trend_query": trend_query,
        "idea_score": idea_score,
        "preflight_status": preflight.get("status"),
        "originality_status": originality.get("status"),
    })
    packet_path = write_prompt_packet(account, trend_query, packet)

    review = run_agent(
        "video_reviewer",
        "Review this prompt packet before generation. Return PASS, REVIEW, or REJECT with specific fixes. Remember: no model can guarantee monetization. Explicitly check AI disclosure, repeated/template risk, voiceover/voice-clone risk, and advertiser suitability.",
        context=json.dumps(packet, ensure_ascii=False, indent=2),
        max_tokens=1500,
    )
    route = run_agent(
        "channel_router",
        "Route this Short to the best configured channel. Return the channel key or manual_review and explain why. If any gate is REJECT, route to manual_review.",
        context=json.dumps({"packet": packet, "accounts": accounts, "review": review}, ensure_ascii=False, indent=2),
        max_tokens=900,
    )

    payload = {
        "trend_payload": trend_payload,
        "prompt_packet": packet,
        "prompt_packet_path": str(packet_path),
        "prompt_version_path": str(prompt_version_path),
        "idea_score": idea_score,
        "preflight": preflight,
        "originality": originality,
        "review": review,
        "route": route,
    }
    payload["run_id"] = save_run(account, "ai_prompt_packet", trend_query, payload)
    return payload


def run_ai_video_chain(account: str, trend_query: str, trend_notes: str | None = None,
                       provider: str = "mock", generate: bool = False,
                       workflow_path: str | Path | None = None,
                       wait: bool = False,
                       use_youtube: bool = True,
                       force: bool = False,
                       voiceover: bool = True,
                       voice_provider: str = "mock") -> dict[str, Any]:
    payload = create_ai_prompt_packet(
        account=account,
        trend_query=trend_query,
        trend_notes=trend_notes,
        use_youtube=use_youtube,
    )
    gates = {
        "preflight": payload.get("preflight", {}),
        "originality": payload.get("originality", {}),
    }
    allowed, block_reasons = generation_allowed(gates)
    generation_result: dict[str, Any] | None = None
    voiceover_result: dict[str, Any] | None = None
    if voiceover and (allowed or force):
        try:
            voiceover_result = generate_voiceover_from_packet(account, payload["prompt_packet_path"], provider=voice_provider)
        except Exception as exc:
            voiceover_result = {"status": "voiceover_failed", "error": str(exc), "provider": voice_provider}
    elif voiceover:
        voiceover_result = {"status": "skipped_due_to_gate", "block_reasons": block_reasons}

    if generate and not allowed and not force:
        generation_result = {"status": "blocked_by_pre_generation_gate", "block_reasons": block_reasons, "note": "Use --force only after manual review."}
    elif generate:
        generation_result = generate_video_from_packet(
            account=account,
            packet_path=payload["prompt_packet_path"],
            provider=provider,
            workflow_path=workflow_path,
            wait=wait,
        )
        metadata = payload["prompt_packet"].get("metadata", {})
        local_file = generation_result.get("local_file")
        if local_file:
            save_video(
                account=account,
                local_file=local_file,
                title=metadata.get("title"),
                description=metadata.get("description"),
                privacy_status="generated_local_private_queue",
                compliance={"prompt_review": payload.get("review"), "route": payload.get("route"), "gates": gates, "voiceover": voiceover_result},
            )
    payload["voiceover_result"] = voiceover_result
    payload["generation_result"] = generation_result
    save_run(account, "ai_video_chain", trend_query, payload)
    return payload
