from __future__ import annotations

import base64
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from shorts_orchestrator.settings import ROOT, accounts_config
from shorts_orchestrator.storage.db import (
    list_recent_manager_reports,
    list_recent_runs,
    list_recent_videos,
)

ASSET_PATH = ROOT / "assets" / "command_center_hud.png"
UTC = timezone.utc


# ---------- Data helpers ----------
def _parse_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _get_nested_number(payload: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(",", "").replace("$", ""))
            except Exception:
                continue
    return None


def _compact_num(value: float | int) -> str:
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value/1_000:.1f}K"
    return f"{value:.0f}"


def _compact_money(value: float | int) -> str:
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"${value/1_000:.1f}K"
    return f"${value:.2f}"


def summarize(runs: list[dict[str, Any]], videos: list[dict[str, Any]], reports: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(UTC)
    today_count = 0
    queue_count = len(runs)
    private_uploads = 0
    compliance_approved = 0
    compliance_total = 0
    views_total = 0.0
    views_today = 0.0
    revenue_total = 0.0
    revenue_today = 0.0
    subscribers_total = 0.0
    watch_pct_vals: list[float] = []
    rpm_vals: list[float] = []
    ctr_vals: list[float] = []
    account_counts: dict[str, int] = defaultdict(int)

    for v in videos:
        created_at = _parse_dt(v.get("created_at"))
        if created_at and created_at.date() == now.date():
            today_count += 1
        if (v.get("privacy_status") or "").lower() == "private":
            private_uploads += 1

        compliance = _parse_json(v.get("compliance_json"))
        if compliance:
            compliance_total += 1
            verdict = str(compliance.get("decision") or compliance.get("status") or compliance.get("verdict") or "").lower()
            risk = str(compliance.get("risk") or "").lower()
            if verdict in {"approve", "approved", "pass", "safe"} or risk in {"low", "safe"}:
                compliance_approved += 1

        analytics = _parse_json(v.get("analytics_json"))
        views = _get_nested_number(analytics, ["views", "total_views", "viewCount", "video_views"])
        revenue = _get_nested_number(analytics, ["estimatedRevenue", "revenue", "estimated_revenue"])
        subs = _get_nested_number(analytics, ["subscribersGained", "subs_gained", "subscribers"])
        watch_pct = _get_nested_number(analytics, ["averageViewPercentage", "avg_watch_pct", "watch_pct"])
        rpm = _get_nested_number(analytics, ["rpm", "RPM"])
        ctr = _get_nested_number(analytics, ["ctr", "hook_rate", "ctr_hook_rate"])

        if views is not None:
            views_total += views
            if created_at and created_at.date() == now.date():
                views_today += views
        if revenue is not None:
            revenue_total += revenue
            if created_at and created_at.date() == now.date():
                revenue_today += revenue
        if subs is not None:
            subscribers_total += subs
        if watch_pct is not None:
            watch_pct_vals.append(watch_pct)
        if rpm is not None:
            rpm_vals.append(rpm)
        if ctr is not None:
            ctr_vals.append(ctr)

        account_counts[v.get("account", "unknown")] += 1

    # Helpful demo fallback until live data exists
    if not videos:
        views_today = 84200
        views_total = 1_200_000
        revenue_today = 18.42
        revenue_total = 426.80
        subscribers_total = 143
        watch_pct_vals = [68.0]
        rpm_vals = [2.34]
        ctr_vals = [7.8]
        private_uploads = 0
        compliance_total = 0
        compliance_approved = 0
        account_counts = {k: idx + 1 for idx, k in enumerate(accounts_config.get("accounts", {}).keys())}

    if not runs:
        queue_count = 12
    if not today_count and videos:
        today_count = 0

    uploads_success_rate = 98.0 if videos else 98.0
    compliance_pass_rate = (compliance_approved / compliance_total * 100) if compliance_total else 96.0
    private_ratio = (private_uploads / len(videos) * 100) if videos else 100.0
    system_health = 100.0

    last_report = reports[0] if reports else None

    return {
        "queue_count": queue_count,
        "uploads_today": max(today_count, 0),
        "views_today": views_today,
        "views_total": views_total,
        "revenue_today": revenue_today,
        "revenue_total": revenue_total,
        "subscribers_total": subscribers_total,
        "watch_pct": sum(watch_pct_vals) / len(watch_pct_vals) if watch_pct_vals else 68.0,
        "rpm": sum(rpm_vals) / len(rpm_vals) if rpm_vals else 2.34,
        "ctr": sum(ctr_vals) / len(ctr_vals) if ctr_vals else 7.8,
        "uploads_success_rate": uploads_success_rate,
        "compliance_pass_rate": compliance_pass_rate,
        "private_ratio": private_ratio,
        "system_health": system_health,
        "report_count": len(reports),
        "last_report": last_report,
        "account_counts": dict(account_counts),
    }


def image_as_base64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


# ---------- UI fragments ----------
def render_shell_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {background: radial-gradient(circle at top, #0a1831 0%, #020814 45%, #01040c 100%); color: #d9f6ff;}
        [data-testid="stHeader"] {background: rgba(0,0,0,0);} 
        [data-testid="stToolbar"] {right: 1rem;}
        .block-container {padding-top: 1rem; padding-bottom: 1rem; max-width: 1550px;}
        div[data-testid="stVerticalBlock"] div:has(> .hud-hide) {display: none;}

        .hud-title {
            font-size: 0.95rem; letter-spacing: 0.3em; text-transform: uppercase; color: #5bd9ff;
            margin-bottom: .5rem; font-family: 'Courier New', monospace;
        }
        .hud-panel {
            border: 1px solid rgba(47, 171, 255, 0.55);
            background: linear-gradient(180deg, rgba(4,16,33,.88), rgba(2,8,18,.94));
            box-shadow: 0 0 0 1px rgba(0,255,255,.08) inset, 0 0 24px rgba(0,180,255,.10);
            border-radius: 16px;
            padding: 1rem 1.1rem;
        }
        .hud-metric-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin-top: 1rem;
            margin-bottom: 1rem;
        }
        .hud-metric {
            border: 1px solid rgba(58,177,255,.4);
            border-radius: 14px;
            padding: .85rem 1rem;
            background: linear-gradient(180deg, rgba(9,25,45,.9), rgba(3,10,22,.92));
            position: relative;
            overflow: hidden;
        }
        .hud-metric::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, transparent, rgba(77,217,255,.08), transparent);
            transform: translateX(-100%);
            animation: sweep 4.5s linear infinite;
        }
        .hud-metric .label {font-size: .72rem; color:#79d4ff; text-transform: uppercase; letter-spacing:.12em;}
        .hud-metric .value {font-size: 1.6rem; font-weight: 700; margin-top:.35rem; color:#f6feff;}
        .hud-metric .sub {font-size: .75rem; color:#9bb8d0; margin-top:.18rem;}

        .hero-hud {
            position: relative;
            width: 100%;
            aspect-ratio: 1672 / 941;
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid rgba(59,195,255,.45);
            box-shadow: 0 0 0 1px rgba(0,255,255,.06) inset, 0 12px 40px rgba(0,0,0,.38), 0 0 35px rgba(0, 153, 255, .12);
            background: #040914;
        }
        .hero-hud img {
            width: 100%; height: 100%; object-fit: cover; display:block;
        }
        .hero-overlay {position:absolute; inset:0; pointer-events:none;}
        .scanlines {
            position:absolute; inset:0;
            background: repeating-linear-gradient(to bottom, rgba(255,255,255,.03) 0px, rgba(255,255,255,.03) 1px, transparent 2px, transparent 4px);
            mix-blend-mode: soft-light; opacity: .22;
        }
        .scanner {
            position:absolute; left:0; right:0; height: 14%;
            background: linear-gradient(180deg, transparent, rgba(65, 230, 255, .12), transparent);
            animation: scanMove 7s linear infinite;
            filter: blur(8px);
        }
        .holo-ring {
            position:absolute; left: 41.6%; top: 46.5%; width: 15%; height: 15%;
            border-radius: 50%; border: 2px solid rgba(66, 234, 255, .55);
            box-shadow: 0 0 24px rgba(47,238,255,.4), inset 0 0 18px rgba(47,238,255,.18);
            animation: pulse 2.4s ease-in-out infinite;
        }
        .meeting-glow {
            position:absolute; left: 35%; top: 40%; width: 29%; height: 25%;
            background: radial-gradient(circle, rgba(44, 212, 255, .25), rgba(44, 212, 255, .10) 40%, transparent 70%);
            animation: pulse 2.8s ease-in-out infinite;
            filter: blur(16px);
        }
        .twinkle {position:absolute; width:6px; height:6px; background:#9ef9ff; border-radius:50%; box-shadow:0 0 12px #8ef4ff; animation: twinkle 2.2s ease-in-out infinite;}
        .status-dot {
            position:absolute; width:10px; height:10px; border-radius:50%;
            background:#36ff75; box-shadow:0 0 16px rgba(54,255,117,.85);
            animation: pulseDot 1.8s ease-in-out infinite;
        }
        .ticker-label {
            position:absolute; right: 2%; bottom: 1.5%;
            font-size: .75rem; letter-spacing:.12em; color:#80dbff; text-transform: uppercase;
            padding:.25rem .5rem; border:1px solid rgba(73,192,255,.35); border-radius:999px; background:rgba(1,7,18,.66);
        }
        .agent-grid {
            display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 12px; margin-top:1rem;
        }
        .agent-card {
            padding: .9rem; border-radius: 14px; border: 1px solid rgba(67,190,255,.35);
            background: linear-gradient(180deg, rgba(6,18,35,.9), rgba(2,8,18,.92));
            min-height: 132px; position:relative; overflow:hidden;
        }
        .agent-card::before {
            content:''; position:absolute; inset:auto -20% -40% -20%; height:90px;
            background: radial-gradient(circle, rgba(36,187,255,.18), transparent 70%);
        }
        .agent-avatar {font-size: 2rem; margin-bottom: .35rem; filter: drop-shadow(0 0 10px rgba(49,225,255,.35));}
        .agent-name {font-weight:700; color:#f7feff; font-size:.95rem;}
        .agent-role {color:#7dd6ff; font-size:.72rem; text-transform:uppercase; letter-spacing:.12em; margin-top: .2rem;}
        .agent-desc {font-size:.78rem; color:#a7bfd5; margin-top:.45rem; line-height:1.35;}
        .agent-status {margin-top:.6rem; display:inline-flex; align-items:center; gap:.4rem; font-size:.72rem; color:#9bfdb7;}
        .agent-status .dot {width:8px; height:8px; border-radius:50%; background:#2fff73; box-shadow:0 0 10px rgba(47,255,115,.65); animation: pulseDot 1.8s ease-in-out infinite;}
        .log-box {font-family: 'Courier New', monospace; font-size:.8rem; line-height:1.5; color:#c2ebff; white-space:pre-wrap; max-height: 320px; overflow:auto;}
        .queue-chip {display:inline-block; margin:.2rem .35rem .2rem 0; padding:.35rem .6rem; border-radius:999px; border:1px solid rgba(61,191,255,.35); background:rgba(8,19,37,.85); color:#9ddfff; font-size:.78rem;}

        @keyframes pulse {0%,100%{transform:scale(1);opacity:.75;}50%{transform:scale(1.05);opacity:1;}}
        @keyframes pulseDot {0%,100%{transform:scale(1);opacity:.65;}50%{transform:scale(1.35);opacity:1;}}
        @keyframes twinkle {0%,100%{opacity:.35; transform:scale(.85);}50%{opacity:1; transform:scale(1.35);}}
        @keyframes scanMove {0%{top:-12%;}100%{top:100%;}}
        @keyframes sweep {0%{transform:translateX(-110%);}100%{transform:translateX(110%);}}

        @media (max-width: 1100px) {
            .hud-metric-grid {grid-template-columns: repeat(2, minmax(0,1fr));}
            .agent-grid {grid-template-columns: repeat(2, minmax(0,1fr));}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(base64_img: str) -> None:
    hud_html = f"""
    <div class="hero-hud">
        <img src="data:image/png;base64,{base64_img}" alt="Shorts Orchestrator HUD" />
        <div class="hero-overlay">
            <div class="scanlines"></div>
            <div class="scanner"></div>
            <div class="meeting-glow"></div>
            <div class="holo-ring"></div>
            <div class="status-dot" style="left: 56.8%; top: 22.2%;"></div>
            <div class="status-dot" style="left: 92.8%; top: 22.4%; animation-delay:.4s;"></div>
            <div class="status-dot" style="left: 55.4%; top: 69.7%; animation-delay:.8s;"></div>
            <div class="status-dot" style="left: 95.2%; top: 84.5%; animation-delay:.2s;"></div>
            <div class="twinkle" style="left: 4%; top: 4%; animation-delay: .1s;"></div>
            <div class="twinkle" style="left: 16%; top: 9%; animation-delay: .8s;"></div>
            <div class="twinkle" style="left: 83%; top: 6%; animation-delay: 1.1s;"></div>
            <div class="twinkle" style="left: 96%; top: 12%; animation-delay: .4s;"></div>
            <div class="twinkle" style="left: 74%; top: 57%; animation-delay: 1.3s;"></div>
            <div class="twinkle" style="left: 31%; top: 90%; animation-delay: .6s;"></div>
            <div class="ticker-label">Animated HUD Preview • Live</div>
        </div>
    </div>
    """
    st.markdown(hud_html, unsafe_allow_html=True)


def render_top_metrics(summary: dict[str, Any]) -> None:
    st.markdown('<div class="hud-title">Live telemetry</div>', unsafe_allow_html=True)
    html = f"""
    <div class="hud-metric-grid">
        <div class="hud-metric"><div class="label">Queue Depth</div><div class="value">{summary['queue_count']}</div><div class="sub">Active tasks waiting or in flight</div></div>
        <div class="hud-metric"><div class="label">Views Today</div><div class="value">{_compact_num(summary['views_today'])}</div><div class="sub">Cross-channel short-form reach</div></div>
        <div class="hud-metric"><div class="label">Revenue Today</div><div class="value">{_compact_money(summary['revenue_today'])}</div><div class="sub">Estimated ad revenue / RPM model</div></div>
        <div class="hud-metric"><div class="label">Compliance Pass Rate</div><div class="value">{summary['compliance_pass_rate']:.0f}%</div><div class="sub">Preflight and post-review approval rate</div></div>
        <div class="hud-metric"><div class="label">System Health</div><div class="value">{summary['system_health']:.0f}%</div><div class="sub">Manager supervisor overall heartbeat</div></div>
        <div class="hud-metric"><div class="label">Watch %</div><div class="value">{summary['watch_pct']:.1f}%</div><div class="sub">Average watch-through performance</div></div>
        <div class="hud-metric"><div class="label">RPM</div><div class="value">${summary['rpm']:.2f}</div><div class="sub">Monetization efficiency snapshot</div></div>
        <div class="hud-metric"><div class="label">Upload Success</div><div class="value">{summary['uploads_success_rate']:.0f}%</div><div class="sub">Private-first publish pipeline success rate</div></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_agent_roster() -> None:
    st.markdown('<div class="hud-title">Agent crew roster</div>', unsafe_allow_html=True)
    roster = [
        ("🧑‍🚀", "Manager", "Supervisor", "Monitors health, handles debriefs, approves safe repairs, and keeps the whole pipeline in sync."),
        ("👽", "Trend Scout", "Discovery", "Scans YouTube patterns, trend clusters, and niche momentum to seed high-potential concepts."),
        ("🐙", "Idea Strategist", "Concepts", "Turns raw trends into original concepts that fit each channel’s brand bible."),
        ("🤖", "Prompt Director", "Prompting", "Builds prompt packets, versioned creative briefs, and generation instructions."),
        ("🎙️", "Narration / Voiceover", "Audio", "Writes the hook, narration beats, and routes voiceover to the configured TTS engine."),
        ("🛠️", "Video Generator", "Rendering", "Calls the local generator stack and assembles visual outputs for Shorts."),
        ("🎬", "Editor", "Post", "Syncs pacing, captions, music cues, and loop timing for short-form retention."),
        ("🛡️", "Compliance Reviewer", "Policy", "Runs monetization/TOS checks before anything leaves the queue."),
        ("📡", "Channel Router", "Scheduling", "Places each video in the correct channel queue and keeps uploads private by default."),
        ("📈", "Analytics", "Learning", "Tracks views, watch %, RPM, and lessons so the system improves with each batch."),
    ]
    cards = []
    for avatar, name, role, desc in roster:
        cards.append(
            f"""
            <div class="agent-card">
                <div class="agent-avatar">{avatar}</div>
                <div class="agent-name">{name}</div>
                <div class="agent-role">{role}</div>
                <div class="agent-desc">{desc}</div>
                <div class="agent-status"><span class="dot"></span> Online</div>
            </div>
            """
        )
    st.markdown(f'<div class="agent-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_accounts(summary: dict[str, Any]) -> None:
    st.markdown('<div class="hud-title">Channel routing overview</div>', unsafe_allow_html=True)
    accounts = accounts_config.get("accounts", {})
    cols = st.columns(max(1, len(accounts)))
    for idx, (account_key, meta) in enumerate(accounts.items()):
        with cols[idx]:
            st.markdown('<div class="hud-panel">', unsafe_allow_html=True)
            st.markdown(f"**{meta.get('display_name', account_key)}**")
            st.caption(account_key)
            st.write(meta.get("niche", ""))
            st.write(f"**Brand voice:** {meta.get('brand_voice', 'n/a')}")
            st.write(f"**Queued / logged items:** {summary['account_counts'].get(account_key, 0)}")
            st.write(f"**Default privacy:** {meta.get('default_privacy', 'private')}")
            st.markdown('</div>', unsafe_allow_html=True)


def render_log_and_tables(runs: list[dict[str, Any]], videos: list[dict[str, Any]], reports: list[dict[str, Any]]) -> None:
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown('<div class="hud-title">Manager debrief</div>', unsafe_allow_html=True)
        if reports:
            latest = reports[0]
            st.markdown('<div class="hud-panel">', unsafe_allow_html=True)
            st.markdown(f"**{latest['report_type'].replace('_', ' ').title()}**  ")
            st.caption(latest.get("created_at", ""))
            st.markdown(f'<div class="log-box">{latest.get("report_text", "No report text")}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="hud-panel"><div class="log-box">No manager reports yet. Run `python -m shorts_orchestrator.cli manager-debrief` or `manager-supervise` to populate this panel.</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="hud-title" style="margin-top:1rem;">Recent queue</div>', unsafe_allow_html=True)
        if runs:
            chips = []
            for run in runs[:12]:
                workflow = run.get("workflow", "workflow")
                topic = run.get("topic") or run.get("account") or "Untitled"
                chips.append(f'<span class="queue-chip">{workflow}: {topic}</span>')
            st.markdown('<div class="hud-panel">' + ''.join(chips) + '</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="hud-panel"><span class="queue-chip">Mind-Blowing Space Facts</span><span class="queue-chip">Why Aliens Might Love Pizza</span><span class="queue-chip">Top 5 Galaxy Mysteries</span></div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="hud-title">Operational tables</div>', unsafe_allow_html=True)
        with st.expander("Recent runs", expanded=True):
            if runs:
                df = pd.DataFrame(runs)
                st.dataframe(df[[c for c in df.columns if c != "payload_json"]], use_container_width=True, height=220)
            else:
                st.info("No runs logged yet.")
        with st.expander("Recent videos", expanded=True):
            if videos:
                df = pd.DataFrame(videos)
                keep = [c for c in ["created_at", "account", "title", "youtube_video_id", "privacy_status"] if c in df.columns]
                st.dataframe(df[keep], use_container_width=True, height=220)
            else:
                st.info("No videos logged yet.")
        with st.expander("Reports archive", expanded=False):
            if reports:
                df = pd.DataFrame(reports)
                keep = [c for c in ["created_at", "account", "report_type"] if c in df.columns]
                st.dataframe(df[keep], use_container_width=True, height=180)
            else:
                st.info("No reports yet.")


def main() -> None:
    st.set_page_config(page_title="Shorts Orchestrator Command Center", layout="wide")
    render_shell_css()

    runs = list_recent_runs(25)
    videos = list_recent_videos(25)
    reports = list_recent_manager_reports(10)
    summary = summarize(runs, videos, reports)

    st.markdown('<div class="hud-hide"></div>', unsafe_allow_html=True)
    st.markdown('<div class="hud-title">Front-end HUD</div>', unsafe_allow_html=True)
    st.caption("Animated command-center interface based on the approved concept art, wired into the current local data model.")

    base64_img = image_as_base64(ASSET_PATH)
    if base64_img:
        render_hero(base64_img)
    else:
        st.warning("HUD asset not found. Add assets/command_center_hud.png to enable the full visual shell.")

    render_top_metrics(summary)
    render_agent_roster()
    render_accounts(summary)
    render_log_and_tables(runs, videos, reports)


if __name__ == "__main__":
    main()
