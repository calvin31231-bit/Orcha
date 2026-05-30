from __future__ import annotations

from pathlib import Path

from shorts_orchestrator.settings import OUTPUTS_DIR


def transcribe_to_srt(video_path: str, model_size: str = "base") -> Path:
    """Optional local transcription using faster-whisper.

    This is intentionally simple. For word-perfect karaoke captions, upgrade to WhisperX or a dedicated subtitle editor.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install faster-whisper or remove transcription from your workflow.") from exc

    path = Path(video_path)
    model = WhisperModel(model_size, device="auto", compute_type="auto")
    segments, _ = model.transcribe(str(path), beam_size=5)
    srt_path = OUTPUTS_DIR / f"{path.stem}.srt"

    def fmt(t: float) -> str:
        ms = int((t - int(t)) * 1000)
        s = int(t) % 60
        m = (int(t) // 60) % 60
        h = int(t) // 3600
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines = []
    for idx, seg in enumerate(segments, start=1):
        text = seg.text.strip()
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{fmt(seg.start)} --> {fmt(seg.end)}")
        lines.append(text)
        lines.append("")
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    return srt_path
