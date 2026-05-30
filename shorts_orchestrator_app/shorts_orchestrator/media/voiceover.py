from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shorts_orchestrator.media.ai_video import read_prompt_packet, safe_slug
from shorts_orchestrator.settings import VOICEOVER_DIR, voiceover_config


def _extract_script(packet: dict[str, Any]) -> str:
    narration = packet.get("voiceover", {}) or packet.get("narration_plan", {}) or packet.get("narration", "")
    if isinstance(narration, dict):
        return narration.get("script") or narration.get("narration_script") or narration.get("voiceover_script") or json.dumps(narration, ensure_ascii=False)
    if isinstance(narration, list):
        return " ".join(str(x) for x in narration)
    return str(narration or packet.get("metadata", {}).get("title") or packet.get("topic") or "")


def _duration_from_text(text: str) -> int:
    words = max(1, len(text.split()))
    return max(4, min(60, int(words / 2.4) + 2))


def create_mock_voiceover(account: str, script: str, title: str) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = VOICEOVER_DIR / f"{account}_{safe_slug(title, 45)}_{stamp}"
    txt = base.with_suffix(".txt")
    wav = base.with_suffix(".wav")
    txt.write_text(script, encoding="utf-8")
    duration = _duration_from_text(script)
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
        "-t", str(duration), str(wav)
    ], check=True)
    return {"provider": "mock", "audio_file": str(wav), "script_file": str(txt), "duration_seconds": duration, "note": "Silent WAV placeholder for testing voiceover sync."}


def create_piper_voiceover(account: str, script: str, title: str) -> dict[str, Any]:
    cfg = voiceover_config.get("voiceover", {}) if isinstance(voiceover_config, dict) else {}
    piper_bin = os.getenv("PIPER_BIN") or cfg.get("piper_bin") or "piper"
    model_path = os.getenv("PIPER_MODEL") or cfg.get("piper_model")
    if not model_path:
        raise FileNotFoundError("Set PIPER_MODEL in .env or config/voiceover.yaml before using provider=piper.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = VOICEOVER_DIR / f"{account}_{safe_slug(title, 45)}_{stamp}_piper.wav"
    subprocess.run([piper_bin, "--model", model_path, "--output_file", str(out)], input=script.encode("utf-8"), check=True)
    return {"provider": "piper", "audio_file": str(out), "script": script}


def create_windows_sapi_voiceover(account: str, script: str, title: str) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        raise RuntimeError("windows_sapi provider only works on Windows.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = VOICEOVER_DIR / f"{account}_{safe_slug(title, 45)}_{stamp}_sapi.wav"
    # Write a temporary PowerShell script to avoid brittle command-line escaping.
    ps_file = VOICEOVER_DIR / f"{account}_{safe_slug(title, 30)}_{stamp}_sapi.ps1"
    escaped_out = str(out).replace("'", "''")
    escaped_script = script.replace("'", "''")
    ps_file.write_text(f"""
$voice = New-Object -ComObject SAPI.SpVoice
$stream = New-Object -ComObject SAPI.SpFileStream
$stream.Open('{escaped_out}', 3, $false)
$voice.AudioOutputStream = $stream
$voice.Rate = 1
$voice.Volume = 95
$voice.Speak('{escaped_script}') | Out-Null
$stream.Close()
""".strip(), encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)], check=True)
    return {"provider": "windows_sapi", "audio_file": str(out), "script": script, "script_runner": str(ps_file)}


def generate_voiceover_from_packet(account: str, packet_path: str | Path, provider: str = "mock") -> dict[str, Any]:
    packet = read_prompt_packet(packet_path)
    title = packet.get("metadata", {}).get("title") or packet.get("topic") or "AI Short"
    script = _extract_script(packet).strip()
    if not script:
        raise ValueError("Prompt packet does not include narration/voiceover script text.")
    if provider == "mock":
        return create_mock_voiceover(account, script, title)
    if provider == "piper":
        return create_piper_voiceover(account, script, title)
    if provider == "windows_sapi":
        return create_windows_sapi_voiceover(account, script, title)
    raise ValueError("Unknown voiceover provider. Use mock, piper, or windows_sapi.")
