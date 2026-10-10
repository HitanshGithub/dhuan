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
MAX_SUBSCRIBERS = 500  # each subscriber is an SNS topic; an open endpoint must not be able to create them without limit
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

    def confirmed(self, sub: dict) -> bool:
        return True

    def by_email(self, email: str) -> list[dict]:
        return [s for s in self.all() if s["email"].lower() == email.lower()]

    def resend_confirmation(self, sub: dict) -> None:
        pass


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

    def confirmed(self, sub: dict) -> bool:
        """SNS drops messages published before the email subscription is confirmed, silently; so check first."""
        subs = self.sns.list_subscriptions_by_topic(TopicArn=sub["topic_arn"])["Subscriptions"]
        return any(s["SubscriptionArn"] != "PendingConfirmation" for s in subs)

    def by_email(self, email: str) -> list[dict]:
        from boto3.dynamodb.conditions import Attr

        items, start = [], None
        while True:
            kwargs = {"FilterExpression": Attr("email").eq(email)}
            if start:
                kwargs["ExclusiveStartKey"] = start
            page = self.table.scan(**kwargs)
            items += page["Items"]
            start = page.get("LastEvaluatedKey")
            if not start:
                return [_plain(i) for i in items]

    def resend_confirmation(self, sub: dict) -> None:
        """Subscribing the same address again makes SNS send a fresh confirmation email."""
        self.sns.subscribe(TopicArn=sub["topic_arn"], Protocol="email", Endpoint=sub["email"])


def _plain(item: dict) -> dict:
    out = dict(item)
    for k in ("lat", "lon"):
        if k in out:
            out[k] = float(out[k])
    return out


def repo():
    return AwsSubscribers() if settings.storage == "s3" else LocalSubscribers()


# --- public API --------------------------------------------------------------------------------------------

SAME_PLACE_DEG = 0.15  # about 15 km: the same person tapping "Delhi" twice lands 9 km apart and means the same subscription


class SubscriptionsFull(Exception):
    """The demo deployment's subscriber cap has been reached."""


def _same_place(subs: list[dict], lat: float, lon: float) -> list[dict]:
    return [s for s in subs if abs(s["lat"] - lat) < SAME_PLACE_DEG and abs(s["lon"] - lon) < SAME_PLACE_DEG]


def subscribe(email: str, lat: float, lon: float, label: str, language: str) -> dict:
    r = repo()
    email = email.strip().lower()
    same_place = _same_place(r.by_email(email), lat, lon)
    if same_place:
        # prefer a confirmed one: the same person may have subscribed twice and confirmed only the first
        existing = next((s for s in same_place if r.confirmed(s)), same_place[0])
        existing["label"], existing["language"] = label.strip()[:80] or existing.get("label", ""), language
        r.put(existing)
        if r.confirmed(existing):
            return {"id": existing["id"], "status": "subscribed", "note": "You were already subscribed for this place, and it is confirmed."}
        r.resend_confirmation(existing)
        return {"id": existing["id"], "status": "pending_confirmation",
                "note": "You subscribed for this place before but never confirmed. We have sent the confirmation email again."}
    if len(r.all()) >= MAX_SUBSCRIBERS:
        raise SubscriptionsFull()
    sub = {"id": uuid.uuid4().hex[:10], "email": email, "lat": lat, "lon": lon, "label": label.strip()[:80], "language": language,
           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "last_alert_at": None, "last_alert_band": None}
    if isinstance(r, AwsSubscribers):
        sub["topic_arn"] = r.create_topic(sub)
        status, note = "pending_confirmation", ("Open the email from AWS Notifications (check spam too) and click \"Confirm subscription\". "
                                                "Until then nothing can be delivered to you.")
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
    target = sub
    if not r.confirmed(sub):
        # the same person may have an older, confirmed subscription (for any place): deliver through that one
        target = next((s for s in r.by_email(sub["email"]) if s["id"] != sub_id and r.confirmed(s)), None)
        if target is None:
            return {"id": sub_id, "sent": False, "status": "pending_confirmation",
                    "reason": "Not confirmed yet. Open the email from AWS Notifications, click \"Confirm subscription\", then press this again."}
    fc = forecast.point_forecast(sub["lat"], sub["lon"])
    if not fc:
        return {"id": sub_id, "sent": False, "status": "no_forecast", "reason": "No forecast for this place yet"}
    message = advisory.compose(fc, sub.get("label", ""), sub.get("language", "en"))
    ref = r.deliver(target, message)
    return {"id": sub_id, "sent": True, "status": "sent", "ref": ref, **message}
