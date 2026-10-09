"""Deploy frontend/dist to AWS Amplify Hosting as a manual deployment (no Git connection needed).

Creates the Amplify app and `main` branch on first run, uploads dist/ as a zip and starts the deployment.

Usage:
  uv run --project backend python infra/deploy_frontend.py --region ap-south-1 --ensure-only   # prints the site URL, deploys nothing
  cd frontend && VITE_API_BASE=<ApiUrl> npm run build
  uv run --project backend python infra/deploy_frontend.py --region ap-south-1

Adapted from the deploy skeleton of my earlier ClaimBack project (MIT).
"""

import argparse
import io
import time
import urllib.request
import zipfile
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
SPA_RULE = {
    "source": "</^[^.]+$|\\.(?!(css|gif|ico|jpg|jpeg|js|mjs|png|txt|svg|woff|woff2|ttf|map|json|webp|geojson|xml|webmanifest)$)([^.]+$)/>",
    "target": "/index.html",
    "status": "200",
}


def zip_dist() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(DIST.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(DIST).as_posix())
    return buffer.getvalue()


def ensure_app(amplify, name: str, branch: str) -> str:
    app = next((a for a in amplify.list_apps()["apps"] if a["name"] == name), None)
    if app:
        amplify.update_app(appId=app["appId"], customRules=[SPA_RULE])
    else:
        app = amplify.create_app(name=name, platform="WEB", customRules=[SPA_RULE],
                                 description="Dhuan - where North India's farm-fire smoke is going")["app"]
        print(f"created app {app['appId']}")
    app_id = app["appId"]
    if not any(b["branchName"] == branch for b in amplify.list_branches(appId=app_id)["branches"]):
        amplify.create_branch(appId=app_id, branchName=branch, stage="PRODUCTION")
        print(f"created branch {branch}")
    return app_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--name", default="dhuan")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--ensure-only", action="store_true", help="create the app and branch if needed, print the URL, deploy nothing")
    args = parser.parse_args()

    amplify = boto3.client("amplify", region_name=args.region)
    app_id = ensure_app(amplify, args.name, args.branch)
    site = f"https://{args.branch}.{app_id}.amplifyapp.com"
    if args.ensure_only:
        print(site)
        return
    if not (DIST / "index.html").exists():
        raise SystemExit(f"{DIST} has no index.html - run `npm run build` first")

    deployment = amplify.create_deployment(appId=app_id, branchName=args.branch)
    payload = zip_dist()
    request = urllib.request.Request(deployment["zipUploadUrl"], data=payload, method="PUT", headers={"Content-Type": "application/zip"})
    with urllib.request.urlopen(request) as response:
        print(f"uploaded {len(payload) / 1e6:.1f} MB ({response.status})")
    job = amplify.start_deployment(appId=app_id, branchName=args.branch, jobId=deployment["jobId"])["jobSummary"]
    while job["status"] in ("PENDING", "RUNNING", "PROVISIONING"):
        time.sleep(5)
        job = amplify.get_job(appId=app_id, branchName=args.branch, jobId=job["jobId"])["job"]["summary"]
    print(f"deployment {job['status']}")
    print(f"\nSite: {site}")


if __name__ == "__main__":
    main()
