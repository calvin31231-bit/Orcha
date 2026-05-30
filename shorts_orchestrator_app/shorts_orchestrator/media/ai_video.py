from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shorts_orchestrator.connectors.comfyui_client import queue_prompt, wait_for_history, save_comfyui_history
from shorts_orchestrator.settings import OUTPUTS_DIR


def safe_slug(text: str, max_len: int = 70) -> str:
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in text.lower()).strip("_")
    return (slug or "ai_short")[:max_len]


def write_prompt_packet(account: str, topic: str, packet: dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = OUTPUTS_DIR / f"{account}_{safe_slug(topic, 40)}_{stamp}_prompt_packet.json"
    out.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def read_prompt_packet(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def create_placeholder_short(account: str, title: str, duration: int = 8) -> Path:
    """Creates a simple generated placeholder MP4 to prove the pipeline works.

    This is not meant to be uploaded as monetizable content. Use ComfyUI/Wan/LTX/Hunyuan
    for real AI generation. The placeholder is useful for testing upload and queue logic.
    """
    out = OUTPUTS_DIR / f"{account}_{safe_slug(title)}_PLACEHOLDER.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={duration}:r=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return out


def generate_video_from_packet(account: str, packet_path: str | Path, provider: str = "mock",
                               workflow_path: str | Path | None = None,
                               wait: bool = False) -> dict[str, Any]:
    packet = read_prompt_packet(packet_path)
    title = packet.get("metadata", {}).get("title") or packet.get("title") or packet.get("topic") or "AI Short"
    prompt = packet.get("video_prompt") or packet.get("prompt") or packet.get("positive_prompt")
    negative_prompt = packet.get("negative_prompt") or ""
    if not prompt:
        raise ValueError("Prompt packet must include 'video_prompt', 'prompt', or 'positive_prompt'.")

    if provider == "mock":
        local_file = create_placeholder_short(account, title)
        return {
            "provider": provider,
            "status": "placeholder_created",
            "local_file": str(local_file),
            "note": "Placeholder proves the pipeline only. Do not treat it as real monetizable content.",
        }

    if provider == "comfyui":
        queued = queue_prompt(prompt=prompt, negative_prompt=negative_prompt, workflow_path=workflow_path)
        prompt_id = queued.get("prompt_id")
        result: dict[str, Any] = {"provider": provider, "status": "queued", "prompt_id": prompt_id, "queue_response": queued}
        if wait and prompt_id:
            history = wait_for_history(prompt_id)
            history_path = save_comfyui_history(account, prompt_id, history)
            result.update({"status": "completed_or_history_available", "history_file": str(history_path)})
        return result

    raise ValueError(f"Unknown video provider '{provider}'. Use mock or comfyui.")
