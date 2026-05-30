from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
INPUTS_DIR = DATA_DIR / "inputs"
OUTPUTS_DIR = DATA_DIR / "outputs"
LOGS_DIR = DATA_DIR / "logs"
DB_DIR = DATA_DIR / "db"
BRAND_BIBLES_DIR = CONFIG_DIR / "brand_bibles"
PROMPT_VERSIONS_DIR = LOGS_DIR / "prompt_versions"
LEARNING_DIR = LOGS_DIR / "learning"
VOICEOVER_DIR = OUTPUTS_DIR / "voiceovers"
QUEUE_DIR = DATA_DIR / "queue"

for path in [CONFIG_DIR, DATA_DIR, INPUTS_DIR, OUTPUTS_DIR, LOGS_DIR, DB_DIR, BRAND_BIBLES_DIR, PROMPT_VERSIONS_DIR, LEARNING_DIR, VOICEOVER_DIR, QUEUE_DIR]:
    path.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass(frozen=True)
class AppSettings:
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    youtube_client_secrets: Path = Path(os.getenv("YOUTUBE_CLIENT_SECRETS", CONFIG_DIR / "client_secret.json"))
    youtube_token_file: Path = Path(os.getenv("YOUTUBE_TOKEN_FILE", CONFIG_DIR / "youtube_token.json"))
    default_upload_privacy: str = os.getenv("DEFAULT_UPLOAD_PRIVACY", "private")
    require_manual_approval: bool = os.getenv("REQUIRE_MANUAL_APPROVAL", "true").lower() == "true"


settings = AppSettings()
models_config = load_yaml(CONFIG_DIR / "models.yaml")
accounts_config = load_yaml(CONFIG_DIR / "accounts.yaml")
policy_config = load_yaml(CONFIG_DIR / "policy_rules.yaml")
voiceover_config = load_yaml(CONFIG_DIR / "voiceover.yaml")
schedule_config = load_yaml(CONFIG_DIR / "posting_schedule.yaml")
