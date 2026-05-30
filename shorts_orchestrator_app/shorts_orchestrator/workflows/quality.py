from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shorts_orchestrator.agents.router import run_agent
from shorts_orchestrator.settings import PROMPT_VERSIONS_DIR, policy_config
from shorts_orchestrator.storage.db import list_recent_runs_by_account


def classify_status(text: str) -> str:
    upper = (text or "").upper()
    if "REJECT" in upper:
        return "REJECT"
    if "REVIEW" in upper:
        return "REVIEW"
    if "PASS" in upper:
        return "PASS"
    return "REVIEW"


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9]{3,}", text.lower()) if t not in {"the", "and", "for", "with", "this", "that"}}


def jaccard_similarity(a: str, b: str) -> float:
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


def score_idea(account: str, shared_context: dict[str, Any], concept_output: str) -> dict[str, Any]:
    task = (
        "Score this YouTube Shorts idea before video generation. Return only valid JSON with keys: "
        "final_score integer 0-100, trend_relevance, hook_strength, visual_novelty, loop_potential, "
        "brand_fit, monetization_safety, production_difficulty, decision GENERATE/REVISE/REJECT, reasons array, fixes array. "
        "Reject or revise weak, repetitive, copyrighted, real-person, or mass-produced ideas."
    )
    raw = run_agent(
        "idea_scorer",
        task,
        context=json.dumps({"account": account, "shared_context": shared_context, "concept_output": concept_output}, ensure_ascii=False, indent=2),
        max_tokens=1200,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        score_match = re.search(r"(\d{1,3})", raw)
        score = max(0, min(100, int(score_match.group(1)))) if score_match else 50
        parsed = {"final_score": score, "decision": "REVISE" if score < 75 else "GENERATE", "raw": raw}
    parsed.setdefault("raw", raw)
    return parsed


def pre_generation_compliance_gate(account: str, shared_context: dict[str, Any], concept_output: str, idea_score: dict[str, Any]) -> dict[str, Any]:
    hard_reject = (policy_config.get("policy_rules", {}) or {}).get("hard_reject_if", [])
    heuristic_flags = []
    lowered = concept_output.lower()
    risky_terms = ["celebrity", "mrbeast", "disney", "pokemon", "marvel", "tiktok compilation", "repost", "deepfake", "clone voice"]
    for term in risky_terms:
        if term in lowered:
            heuristic_flags.append(f"Risky term found: {term}")
    task = (
        "Run a pre-generation YouTube policy gate on this Shorts concept. Return PASS, REVIEW, or REJECT, "
        "then a bullet list of specific fixes. Be conservative about reused content, repetitive/mass-produced content, "
        "copyright/IP, real-person likeness, cloned voices, kids-content, fake realistic events, and advertiser suitability."
    )
    raw = run_agent(
        "preflight_compliance",
        task,
        context=json.dumps({
            "account": account,
            "shared_context": shared_context,
            "concept_output": concept_output,
            "idea_score": idea_score,
            "hard_reject_rules": hard_reject,
            "heuristic_flags": heuristic_flags,
        }, ensure_ascii=False, indent=2),
        max_tokens=1200,
    )
    status = classify_status(raw)
    if heuristic_flags and status == "PASS":
        status = "REVIEW"
    final_score = int(idea_score.get("final_score", 50) or 50)
    if final_score < 60:
        status = "REJECT"
    elif final_score < 75 and status == "PASS":
        status = "REVIEW"
    return {"status": status, "review": raw, "heuristic_flags": heuristic_flags}


def originality_check(account: str, candidate_text: str, limit: int = 30, threshold: float = 0.42) -> dict[str, Any]:
    recent = list_recent_runs_by_account(account, limit=limit)
    best = {"similarity": 0.0, "run_id": None, "topic": None}
    for row in recent:
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except json.JSONDecodeError:
            payload = {}
        previous_text = json.dumps(payload, ensure_ascii=False)
        sim = jaccard_similarity(candidate_text, previous_text)
        if sim > best["similarity"]:
            best = {"similarity": sim, "run_id": row.get("id"), "topic": row.get("topic")}
    status = "PASS"
    if best["similarity"] >= threshold:
        status = "REVIEW"
    if best["similarity"] >= 0.62:
        status = "REJECT"
    raw = run_agent(
        "originality_checker",
        "Check whether this new Short is too similar to previous account output. Return PASS, REVIEW, or REJECT with fixes to increase originality.",
        context=json.dumps({"candidate_text": candidate_text[:5000], "best_similarity_match": best}, ensure_ascii=False, indent=2),
        max_tokens=900,
    )
    model_status = classify_status(raw)
    if model_status == "REJECT" or status == "REJECT":
        status = "REJECT"
    elif model_status == "REVIEW" or status == "REVIEW":
        status = "REVIEW"
    return {"status": status, "best_match": best, "review": raw}


def write_prompt_version_log(account: str, packet: dict[str, Any], meta: dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    serial = json.dumps(packet, sort_keys=True, ensure_ascii=False)
    version_hash = hashlib.sha256(serial.encode("utf-8")).hexdigest()[:12]
    out_dir = PROMPT_VERSIONS_DIR / account
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stamp}_{version_hash}.json"
    payload = {"version_hash": version_hash, "created_at_utc": stamp, "meta": meta, "packet": packet}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def generation_allowed(gates: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    for name, gate in gates.items():
        status = (gate or {}).get("status") or (gate or {}).get("decision")
        if isinstance(status, str) and status.upper() == "REJECT":
            reasons.append(f"{name}=REJECT")
    return (len(reasons) == 0), reasons
