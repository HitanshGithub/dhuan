"""Subscriptions and alerts.

Deployed: subscribers live in DynamoDB and each one gets their own SNS topic with an email subscription, so
SNS handles confirmation and unsubscribe links. Locally: a JSON file, and "sent" emails land in out/outbox.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone

from . import advisory, forecast
from .config import settings
from .storage import storage

log = logging.getLogger(__name__)
ALERT_FROM = "moderate"  # tell people when at least this band is coming
ALERT_WINDOW_FRAMES = 36  # hours ahead worth warning about
RENOTIFY_HOURS = 18
BAND_ORDER = ["clear", "light", "moderate", "heavy", "severe"]


# --- persistence -------------------------------------------------------------------------------------------

class LocalSubscribers:
    KEY = "subscribers.json"

    def __init__(self):
        self.store = storage()

    def all(self) -> list[dict]:
        raw = self.store.get(self.KEY)
        return json.loads(raw) if raw else []

    def get(self, sub_id: str) -> dict | None:
        return next((s for s in self.all() if s["id"] == sub_id), None)

    def put(self, sub: dict) -> None:
        subs = [s for s in self.all() if s["id"] != sub["id"]] + [sub]
        self.store.put(self.KEY, json.dumps(subs, ensure_ascii=False, indent=1).encode("utf-8"))

    def deliver(self, sub: dict, message: dict) -> str:
        key = f"outbox/{sub['id']}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.txt"
        self.store.put(key, f"To: {sub['email']}\nSubject: {message['subject']}\n\n{message['body']}".encode("utf-8"))
        return key


class AwsSubscribers:
    def __init__(self):
        import boto3

        self.table = boto3.resource("dynamodb", region_name=settings.region).Table(settings.table)
        self.sns = boto3.client("sns", region_name=settings.region)

    def all(self) -> list[dict]:
        items, start = [], None
        while True:
            page = self.table.scan(**({"ExclusiveStartKey": start} if start else {}))
            items += page["Items"]
            start = page.get("LastEvaluatedKey")
            if not start:
                return [_plain(i) for i in items]

    def get(self, sub_id: str) -> dict | None:
        item = self.table.get_item(Key={"id": sub_id}).get("Item")
        return _plain(item) if item else None

    def put(self, sub: dict) -> None:
        self.table.put_item(Item={k: (str(v) if isinstance(v, float) else v) for k, v in sub.items()})

    def create_topic(self, sub: dict) -> str:
        arn = self.sns.create_topic(Name=f"dhuan-sub-{sub['id']}", Tags=[{"Key": "app", "Value": "dhuan"}])["TopicArn"]
        self.sns.subscribe(TopicArn=arn, Protocol="email", Endpoint=sub["email"])
        return arn

    def deliver(self, sub: dict, message: dict) -> str:
        subject = re.sub(r"[^\x20-\x7E]", "", message["subject"])[:99] or "Dhuan smoke alert"  # SNS subjects must be ASCII
        return self.sns.publish(TopicArn=sub["topic_arn"], Subject=subject, Message=message["body"])["MessageId"]


def _plain(item: dict) -> dict:
    out = dict(item)
    for k in ("lat", "lon"):
        if k in out:
            out[k] = float(out[k])
    return out


def repo():
    return AwsSubscribers() if settings.storage == "s3" else LocalSubscribers()


# --- public API --------------------------------------------------------------------------------------------

def subscribe(email: str, lat: float, lon: float, label: str, language: str) -> dict:
    r = repo()
    sub = {"id": uuid.uuid4().hex[:10], "email": email, "lat": lat, "lon": lon, "label": label.strip()[:80], "language": language,
           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "last_alert_at": None, "last_alert_band": None}
    if isinstance(r, AwsSubscribers):
        sub["topic_arn"] = r.create_topic(sub)
        status, note = "pending_confirmation", "Check your inbox for a confirmation email from Amazon SNS and click the link."
    else:
        status, note = "subscribed", "Local build: alerts are written to backend/out/outbox instead of being emailed."
    r.put(sub)
    return {"id": sub["id"], "status": status, "note": note}


def should_alert(sub: dict, fc: dict, now: datetime) -> bool:
    ahead = fc["frames"][fc["peak"]["frame"]] if fc["peak"]["frame"] - _now_frame(fc) <= ALERT_WINDOW_FRAMES else None
    if ahead is None or BAND_ORDER.index(ahead["band"]) < BAND_ORDER.index(ALERT_FROM):
        return False
    if sub.get("last_alert_at"):
        hours = (now - datetime.fromisoformat(sub["last_alert_at"])).total_seconds() / 3600
        worse = BAND_ORDER.index(ahead["band"]) > BAND_ORDER.index(sub.get("last_alert_band") or "clear")
        if hours < RENOTIFY_HOURS and not worse:
            return False
    return True


def _now_frame(fc: dict) -> int:
    return next(i for i, f in enumerate(fc["frames"]) if f["is_now"])


def step_alerts(run_id: str | None = None) -> dict:
    r = repo()
    run = forecast.latest_run()
    now = datetime.now(timezone.utc)
    checked = sent = 0
    for sub in r.all():
        checked += 1
        fc = forecast.point_forecast(sub["lat"], sub["lon"], run)
        if not fc or not should_alert(sub, fc, now):
            continue
        message = advisory.compose(fc, sub.get("label", ""), sub.get("language", "en"))
        try:
            r.deliver(sub, message)
        except Exception:  # an unconfirmed topic, a bad address: carry on with the others
            log.exception("could not deliver to %s", sub["id"])
            continue
        sub["last_alert_at"], sub["last_alert_band"] = now.isoformat(timespec="seconds"), fc["peak"]["key"]
        r.put(sub)
        sent += 1
    return {"run_id": run_id or (run.meta["run_id"] if run else None), "checked": checked, "sent": sent}


def send_now(sub_id: str) -> dict | None:
    """The demo button: this subscriber's advisory for the current forecast, immediately."""
    r = repo()
    sub = r.get(sub_id)
    if not sub:
        return None
    fc = forecast.point_forecast(sub["lat"], sub["lon"])
    if not fc:
        return {"id": sub_id, "sent": False, "reason": "No forecast for this place yet"}
    message = advisory.compose(fc, sub.get("label", ""), sub.get("language", "en"))
    ref = r.deliver(sub, message)
    return {"id": sub_id, "sent": True, "ref": ref, **message}
