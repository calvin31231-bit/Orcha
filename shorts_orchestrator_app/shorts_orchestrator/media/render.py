from __future__ import annotations

import subprocess
from pathlib import Path

from shorts_orchestrator.settings import OUTPUTS_DIR


def _ts_to_seconds(ts: str) -> float:
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)


def render_vertical_clip(
    source: str,
    start: str,
    end: str,
    title: str,
    account: str,
    subtitles_srt: str | None = None,
) -> Path:
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(f"Source video not found: {src}")

    duration = max(0.1, _ts_to_seconds(end) - _ts_to_seconds(start))
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title.lower())[:70]
    out = OUTPUTS_DIR / f"{account}_{safe_title}.mp4"

    # 9:16 crop/scale. This keeps center crop; later you can add face/object tracking.
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    if subtitles_srt:
        sub = Path(subtitles_srt).resolve()
        if sub.exists():
            vf += f",subtitles='{str(sub).replace(chr(39), r"\'")}'"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", start,
        "-i", str(src),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return out
