from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from shorts_orchestrator.settings import CONFIG_DIR, OUTPUTS_DIR


def _replace_placeholders(obj: Any, prompt: str, negative_prompt: str) -> Any:
    if isinstance(obj, str):
        return obj.replace("__PROMPT__", prompt).replace("__NEGATIVE_PROMPT__", negative_prompt)
    if isinstance(obj, list):
        return [_replace_placeholders(x, prompt, negative_prompt) for x in obj]
    if isinstance(obj, dict):
        return {k: _replace_placeholders(v, prompt, negative_prompt) for k, v in obj.items()}
    return obj


def load_workflow(path: str | Path | None = None) -> dict[str, Any]:
    workflow_path = Path(path) if path else CONFIG_DIR / "comfyui_text_to_video_workflow.json"
    if not workflow_path.exists():
        raise FileNotFoundError(f"ComfyUI workflow not found: {workflow_path}")
    with workflow_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def queue_prompt(prompt: str, negative_prompt: str = "", workflow_path: str | Path | None = None,
                 host: str | None = None, client_id: str | None = None) -> dict[str, Any]:
    """Queue a prompt in ComfyUI using an API-format workflow.

    This is intentionally generic. Export an API workflow from ComfyUI, put __PROMPT__ and
    __NEGATIVE_PROMPT__ inside the appropriate nodes, then call this function.
    """
    host = (host or os.getenv("COMFYUI_HOST") or "http://127.0.0.1:8188").rstrip("/")
    workflow = load_workflow(workflow_path)
    workflow = _replace_placeholders(workflow, prompt, negative_prompt)
    # Remove README key if the template still contains it; ComfyUI prompt graphs are node dicts.
    workflow.pop("README", None)
    client_id = client_id or str(uuid.uuid4())
    response = requests.post(f"{host}/prompt", json={"prompt": workflow, "client_id": client_id}, timeout=30)
    response.raise_for_status()
    return response.json()


def wait_for_history(prompt_id: str, host: str | None = None, timeout_seconds: int = 900,
                     poll_seconds: float = 2.0) -> dict[str, Any]:
    host = (host or os.getenv("COMFYUI_HOST") or "http://127.0.0.1:8188").rstrip("/")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{host}/history/{prompt_id}", timeout=30)
        response.raise_for_status()
        payload = response.json()
        if prompt_id in payload:
            return payload[prompt_id]
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for ComfyUI prompt_id={prompt_id}")


def save_comfyui_history(account: str, prompt_id: str, history: dict[str, Any]) -> Path:
    out = OUTPUTS_DIR / f"{account}_comfyui_history_{prompt_id}.json"
    out.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
