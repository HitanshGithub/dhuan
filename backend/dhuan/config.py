"""Settings from environment variables. The defaults run everything locally, with no AWS account."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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


settings = Settings()
