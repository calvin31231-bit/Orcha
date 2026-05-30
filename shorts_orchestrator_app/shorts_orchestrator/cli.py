from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shorts_orchestrator.connectors.youtube_client import get_credentials, get_channel_basic_analytics, upload_video
from shorts_orchestrator.media.render import render_vertical_clip
from shorts_orchestrator.media.ai_video import generate_video_from_packet
from shorts_orchestrator.media.transcribe import transcribe_to_srt
from shorts_orchestrator.media.voiceover import generate_voiceover_from_packet
from shorts_orchestrator.settings import accounts_config, settings
from shorts_orchestrator.storage.db import list_recent_runs, list_recent_videos, save_video
from shorts_orchestrator.workflows.planner import compliance_review, get_account, plan_short
from shorts_orchestrator.workflows.trends import scan_youtube_trends
from shorts_orchestrator.workflows.ai_pipeline import create_ai_prompt_packet, run_ai_video_chain
from shorts_orchestrator.workflows.analytics_loop import update_channel_learning
from shorts_orchestrator.workflows.daily_batch import run_daily_batch
from shorts_orchestrator.workflows.manager_ops import manager_health_check, daily_debrief, model_upgrade_scan, manager_supervise

console = Console()



def cmd_ai_packet(args: argparse.Namespace) -> None:
    result = create_ai_prompt_packet(
        account=args.account,
        trend_query=args.query,
        trend_notes=args.notes,
        max_results=args.max_results,
        use_youtube=not args.no_youtube,
    )
    console.print(Panel(result["review"], title=f"AI Prompt Packet Review #{result['run_id']}"))
    console.print(f"Prompt packet saved: {result['prompt_packet_path']}")
    console.print(Panel(result["route"], title="Channel Router"))


def cmd_ai_chain(args: argparse.Namespace) -> None:
    result = run_ai_video_chain(
        account=args.account,
        trend_query=args.query,
        trend_notes=args.notes,
        provider=args.provider,
        generate=args.generate,
        workflow_path=args.workflow,
        wait=args.wait,
        use_youtube=not args.no_youtube,
        force=args.force,
        voiceover=not args.no_voiceover,
        voice_provider=args.voice_provider,
    )
    console.print(Panel(result["review"], title="AI#4 Review"))
    console.print(Panel(result["route"], title="AI#5 Channel Route"))
    console.print(f"Prompt packet saved: {result['prompt_packet_path']}")
    if result.get("generation_result"):
        console.print_json(data=result["generation_result"])


def cmd_generate_video(args: argparse.Namespace) -> None:
    result = generate_video_from_packet(
        account=args.account,
        packet_path=args.packet,
        provider=args.provider,
        workflow_path=args.workflow,
        wait=args.wait,
    )
    console.print_json(data=result)


def cmd_voiceover(args: argparse.Namespace) -> None:
    result = generate_voiceover_from_packet(args.account, args.packet, provider=args.provider)
    console.print_json(data=result)


def cmd_learn_analytics(args: argparse.Namespace) -> None:
    result = update_channel_learning(args.account, args.start, args.end)
    console.print(Panel(result["lessons"], title=f"Analytics Lessons #{result['snapshot_id']}"))
    console.print(f"Saved learning notes: {result['notes_path']}")


def cmd_daily_batch(args: argparse.Namespace) -> None:
    queries = args.query or []
    if args.queries_file:
        queries += [line.strip() for line in Path(args.queries_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not queries:
        raise SystemExit("Provide at least one --query or --queries-file line.")
    result = run_daily_batch(
        account=args.account,
        queries=queries,
        generate=args.generate,
        provider=args.provider,
        workflow_path=args.workflow,
        wait=args.wait,
        use_youtube=not args.no_youtube,
        force=args.force,
        voiceover=not args.no_voiceover,
        voice_provider=args.voice_provider,
    )
    console.print_json(data={"schedule_guardrails": result["schedule_guardrails"], "processed": result["queries_processed"]})


def cmd_manager_check(args: argparse.Namespace) -> None:
    result = manager_health_check(repair=args.repair, smoke_test=args.smoke_test, packet_limit=args.packet_limit)
    console.print(Panel(result["status"], title="Manager Health Status"))
    console.print_json(data=result)


def cmd_manager_debrief(args: argparse.Namespace) -> None:
    result = daily_debrief(account=args.account, start=args.start, end=args.end, pull_analytics=args.pull_analytics, days=args.days)
    console.print(Panel(result["report"], title=f"Manager Daily Debrief #{result['report_id']}"))
    console.print(f"Saved report: {result['report_path']}")


def cmd_manager_upgrade_scan(args: argparse.Namespace) -> None:
    result = model_upgrade_scan()
    console.print_json(data=result)


def cmd_manager_supervise(args: argparse.Namespace) -> None:
    result = manager_supervise(account=args.account, repair=args.repair, pull_analytics=args.pull_analytics, smoke_test=args.smoke_test, days=args.days)
    console.print(Panel(result["health"]["status"], title="Manager Supervise Status"))
    console.print_json(data=result)

def cmd_plan(args: argparse.Namespace) -> None:
    result = plan_short(args.account, args.topic, args.notes)
    console.print(Panel(result["final"], title=f"Production Brief #{result['run_id']}"))


def cmd_compliance(args: argparse.Namespace) -> None:
    result = compliance_review(args.account, args.title, args.description, args.source_rights, args.script)
    console.print(Panel(result["review"], title=f"Compliance Review #{result['run_id']}"))


def cmd_trends(args: argparse.Namespace) -> None:
    result = scan_youtube_trends(args.account, args.query, args.max_results, args.creative_commons_only)
    console.print(Panel(result["analysis"], title=f"Trend Scan #{result['run_id']}"))


def cmd_render(args: argparse.Namespace) -> None:
    srt = None
    if args.transcribe:
        srt = str(transcribe_to_srt(args.source, model_size=args.whisper_model))
        console.print(f"Created subtitles: {srt}")
    output = render_vertical_clip(args.source, args.start, args.end, args.title, args.account, subtitles_srt=srt)
    save_video(args.account, str(output), args.title, None, privacy_status="local")
    console.print(f"Rendered: {output}")


def confirm_or_abort(action: str) -> None:
    if not settings.require_manual_approval:
        return
    answer = input(f"Manual approval required for {action}. Type APPROVE to continue: ").strip()
    if answer != "APPROVE":
        raise SystemExit("Aborted by user.")


def cmd_upload(args: argparse.Namespace) -> None:
    acct = get_account(args.account)
    privacy = args.privacy or acct.get("default_privacy") or settings.default_upload_privacy
    if privacy != "private":
        confirm_or_abort(f"uploading with privacy={privacy}")
    else:
        console.print("Uploading as private. Review in YouTube Studio before publishing.")
    video_id = upload_video(
        file_path=args.file,
        title=args.title,
        description=args.description,
        tags=args.tags or [],
        privacy_status=privacy,
        made_for_kids=args.made_for_kids or bool(acct.get("made_for_kids", False)),
        category_id=str(acct.get("category_id", "22")),
        notify_subscribers=False,
    )
    save_video(args.account, args.file, args.title, args.description, video_id, privacy)
    console.print(f"Uploaded video ID: {video_id} privacy={privacy}")


def cmd_auth_youtube(args: argparse.Namespace) -> None:
    get_credentials()
    console.print("YouTube OAuth token saved.")


def cmd_analytics(args: argparse.Namespace) -> None:
    end = args.end or date.today().isoformat()
    start = args.start or (date.today() - timedelta(days=7)).isoformat()
    result = get_channel_basic_analytics(start, end)
    console.print_json(data=result)


def cmd_status(args: argparse.Namespace) -> None:
    table = Table(title="Configured Accounts")
    table.add_column("Key")
    table.add_column("Display Name")
    table.add_column("Niche")
    for key, value in (accounts_config.get("accounts") or {}).items():
        table.add_row(key, value.get("display_name", ""), value.get("niche", ""))
    console.print(table)
    console.print("\nRecent runs:")
    console.print_json(data=list_recent_runs(5))
    console.print("\nRecent videos:")
    console.print_json(data=list_recent_videos(5))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local YouTube Shorts Orchestrator")
    sub = parser.add_subparsers(required=True)


    p = sub.add_parser("ai-packet", help="AI#1-#2-#3: trend scan and create an AI video prompt packet")
    p.add_argument("--account", required=True)
    p.add_argument("--query", required=True, help="Trend/topic query, e.g. cute dog fails, cozy fantasy machines")
    p.add_argument("--notes", help="Manual trend notes if you do not want to use YouTube API")
    p.add_argument("--max-results", type=int, default=5)
    p.add_argument("--no-youtube", action="store_true", help="Skip YouTube API trend scan and use local notes/account context only")
    p.set_defaults(func=cmd_ai_packet)

    p = sub.add_parser("ai-chain", help="Run AI#1-#5 chain; optionally generate a local/ComfyUI video")
    p.add_argument("--account", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--notes")
    p.add_argument("--provider", choices=["mock", "comfyui"], default="mock")
    p.add_argument("--generate", action="store_true", help="Actually run provider generation after packet/review")
    p.add_argument("--workflow", help="Optional ComfyUI API workflow JSON path")
    p.add_argument("--wait", action="store_true", help="For ComfyUI, wait for history result")
    p.add_argument("--no-youtube", action="store_true", help="Skip YouTube API trend scan")
    p.add_argument("--force", action="store_true", help="Override REJECT gates after manual review; not recommended for automation")
    p.add_argument("--no-voiceover", action="store_true", help="Skip narration/voiceover generation")
    p.add_argument("--voice-provider", choices=["mock", "piper", "windows_sapi"], default="mock")
    p.set_defaults(func=cmd_ai_chain)

    p = sub.add_parser("generate-video", help="Generate/queue video from an existing prompt packet")
    p.add_argument("--account", required=True)
    p.add_argument("--packet", required=True, help="Path to prompt packet JSON")
    p.add_argument("--provider", choices=["mock", "comfyui"], default="mock")
    p.add_argument("--workflow", help="Optional ComfyUI API workflow JSON path")
    p.add_argument("--wait", action="store_true")
    p.set_defaults(func=cmd_generate_video)

    p = sub.add_parser("voiceover", help="Generate narration audio from an existing prompt packet")
    p.add_argument("--account", required=True)
    p.add_argument("--packet", required=True)
    p.add_argument("--provider", choices=["mock", "piper", "windows_sapi"], default="mock")
    p.set_defaults(func=cmd_voiceover)

    p = sub.add_parser("daily-batch", help="Create a safe daily private-upload candidate batch")
    p.add_argument("--account", required=True)
    p.add_argument("--query", action="append", help="Trend/topic query. Repeat for multiple candidates.")
    p.add_argument("--queries-file", help="Text file with one query per line")
    p.add_argument("--provider", choices=["mock", "comfyui"], default="mock")
    p.add_argument("--generate", action="store_true")
    p.add_argument("--workflow")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--no-youtube", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-voiceover", action="store_true")
    p.add_argument("--voice-provider", choices=["mock", "piper", "windows_sapi"], default="mock")
    p.set_defaults(func=cmd_daily_batch)

    p = sub.add_parser("plan", help="Plan a monetization-aware Short")
    p.add_argument("--account", required=True)
    p.add_argument("--topic", required=True)
    p.add_argument("--notes")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("trends", help="Scan YouTube through official API and analyze patterns")
    p.add_argument("--account", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument("--creative-commons-only", action="store_true")
    p.set_defaults(func=cmd_trends)

    p = sub.add_parser("compliance", help="Run policy/monetization risk review")
    p.add_argument("--account", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--source-rights", required=True, help="Example: original footage, licensed stock, written permission, Creative Commons with attribution")
    p.add_argument("--script")
    p.set_defaults(func=cmd_compliance)

    p = sub.add_parser("render", help="Render a vertical 9:16 clip from local authorized footage")
    p.add_argument("--source", required=True)
    p.add_argument("--start", required=True, help="HH:MM:SS, MM:SS, or seconds")
    p.add_argument("--end", required=True, help="HH:MM:SS, MM:SS, or seconds")
    p.add_argument("--title", required=True)
    p.add_argument("--account", required=True)
    p.add_argument("--transcribe", action="store_true")
    p.add_argument("--whisper-model", default="base")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("auth-youtube", help="Authenticate YouTube OAuth")
    p.set_defaults(func=cmd_auth_youtube)

    p = sub.add_parser("upload", help="Upload video to YouTube, private by default")
    p.add_argument("--file", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--account", required=True)
    p.add_argument("--privacy", choices=["private", "unlisted", "public"])
    p.add_argument("--tags", nargs="*")
    p.add_argument("--made-for-kids", action="store_true")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("analytics", help="Pull channel analytics")
    p.add_argument("--start")
    p.add_argument("--end")
    p.set_defaults(func=cmd_analytics)

    p = sub.add_parser("learn-analytics", help="Pull analytics and update channel learning notes")
    p.add_argument("--account", required=True)
    p.add_argument("--start")
    p.add_argument("--end")
    p.set_defaults(func=cmd_learn_analytics)

    p = sub.add_parser("manager-check", help="Run Manager health checks for configs, models, queues, and handoffs")
    p.add_argument("--repair", action="store_true", help="Apply safe repairs only: create missing folders and brand-bible skeletons")
    p.add_argument("--smoke-test", action="store_true", help="Call the configured Manager model once to verify agent routing")
    p.add_argument("--packet-limit", type=int, default=25)
    p.set_defaults(func=cmd_manager_check)

    p = sub.add_parser("manager-debrief", help="Create a daily operations debrief report")
    p.add_argument("--account", help="Optional channel key; omit for all channels")
    p.add_argument("--start", help="Analytics start date YYYY-MM-DD")
    p.add_argument("--end", help="Analytics end date YYYY-MM-DD")
    p.add_argument("--pull-analytics", action="store_true", help="Pull YouTube Analytics and update learning notes")
    p.add_argument("--days", type=int, default=1, help="Local recent-run window for the debrief")
    p.set_defaults(func=cmd_manager_debrief)

    p = sub.add_parser("manager-upgrade-scan", help="Compare configured AI models with installed/local models and show safe upgrade recommendations")
    p.set_defaults(func=cmd_manager_upgrade_scan)

    p = sub.add_parser("manager-supervise", help="Run health check, daily debrief, and model upgrade scan")
    p.add_argument("--account", help="Optional channel key; omit for all channels")
    p.add_argument("--repair", action="store_true", help="Apply safe local repairs during health check")
    p.add_argument("--pull-analytics", action="store_true", help="Pull YouTube Analytics during debrief")
    p.add_argument("--smoke-test", action="store_true", help="Call the configured Manager model once to verify agent routing")
    p.add_argument("--days", type=int, default=1)
    p.set_defaults(func=cmd_manager_supervise)

    p = sub.add_parser("status", help="Show configured accounts and recent runs")
    p.set_defaults(func=cmd_status)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
