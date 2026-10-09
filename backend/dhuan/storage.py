"""Where a run's outputs live: a folder on disk locally, an S3 bucket behind CloudFront when deployed."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import settings

CONTENT_TYPES = {".json": "application/json", ".png": "image/png", ".npy": "application/octet-stream",
                 ".npz": "application/octet-stream", ".geojson": "application/geo+json"}


def content_type(key: str) -> str:
    return CONTENT_TYPES.get(Path(key).suffix, "application/octet-stream")


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def put(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        path = self.root / key
        return path.read_bytes() if path.exists() else None


class S3Storage:
    def __init__(self, bucket: str, region: str):
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    def put(self, key: str, data: bytes) -> None:
        cache = "no-cache" if key.endswith("latest.json") else "public, max-age=86400, immutable"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type(key), CacheControl=cache)

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None


def put_json(store, key: str, obj) -> None:
    store.put(key, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def get_json(store, key: str):
    raw = store.get(key)
    return json.loads(raw.decode("utf-8")) if raw is not None else None


@lru_cache(maxsize=1)
def storage():
    if settings.storage == "s3":
        return S3Storage(settings.bucket, settings.region)
    return LocalStorage(settings.out_dir)
