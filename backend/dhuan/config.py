"""Settings from environment variables. The defaults run everything locally, with no AWS account."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Local secrets (API keys) live in an untracked .env file; deployed, they come from the Lambda environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    storage: str = _env("DHUAN_STORAGE", "local")  # local | s3
    bucket: str = _env("DHUAN_BUCKET")
    table: str = _env("DHUAN_TABLE")
    region: str = _env("DHUAN_REGION", "ap-south-1")
    llm: str = _env("DHUAN_LLM", "offline")  # offline | bedrock
    model_id: str = _env("DHUAN_MODEL", "mistral.ministral-3-14b-instruct")
    data_dir: Path = Path(_env("DHUAN_DATA_DIR", str(ROOT / "data")))
    out_dir: Path = Path(_env("DHUAN_OUT_DIR", str(ROOT / "backend" / "out")))
    data_url: str = _env("DHUAN_DATA_URL", "/data")  # where the browser fetches run outputs (CloudFront when deployed)
    state_machine_arn: str = _env("DHUAN_STATE_MACHINE_ARN")
    frontend_origin: str = _env("DHUAN_FRONTEND_ORIGIN", "http://localhost:5173")
    firms_window: str = _env("DHUAN_FIRMS_WINDOW", "48h")  # 24h | 48h | 7d
    waqi_token: str = _env("DHUAN_WAQI_TOKEN") or _env("WAQI_TOKEN")  # observed station readings; empty disables them
    firms_map_key: str = _env("FIRMS_MAP_KEY")  # only for building replays of past days (dhuan.replay)


settings = Settings()
