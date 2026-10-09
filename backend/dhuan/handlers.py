"""Lambda entry points.

  api_handler   - the FastAPI app behind API Gateway (Mangum)
  step_handler  - one pipeline step for Step Functions: {"step": "fetch" | "simulate" | "alerts", "run_id"?: "..."}
"""

from __future__ import annotations

import logging

from mangum import Mangum

from . import alerts, run
from .api import app

logging.getLogger().setLevel(logging.INFO)

api_handler = Mangum(app, lifespan="off")


def step_handler(event: dict, context=None) -> dict:
    step = event["step"]
    run_id = event.get("run_id") or run.run_id_for(run.floor_hour())
    if step == "fetch":
        return run.step_fetch(run_id)
    if step == "simulate":
        return run.step_simulate(run_id)
    if step == "alerts":
        return alerts.step_alerts(run_id)
    raise ValueError(f"unknown step {step!r}")
