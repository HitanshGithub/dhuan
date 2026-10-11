# Deploying Dhuan to AWS

Region: **ap-south-1 (Mumbai)**. Everything is one CloudFormation stack (`infra/template.yaml`, SAM syntax) plus an
Amplify Hosting app for the site.

| What | Where |
|---|---|
| Site (Amplify Hosting) | https://main.d9com2kyiohi6.amplifyapp.com |
| API (API Gateway + Lambda) | `ApiUrl` output of the stack |
| Frames and run metadata | `DataUrl` output (CloudFront in front of the private S3 bucket) |
| Stack | `dhuan` |
| Hourly run | Step Functions `ForecastStateMachine`, started by an EventBridge schedule `rate(1 hour)` |

## From this machine

The SAM CLI cannot run on this laptop (an application-control policy blocks Python's `_multiprocessing`), so the
AWS CLI does the same job with `package` + `deploy`:

```bash
cd backend && uv run python scripts/build_lambda.py && cd ..          # Linux wheels, no Docker
aws s3 mb s3://dhuan-deploy-<account-id> --region ap-south-1          # once
aws cloudformation package --template-file infra/template.yaml --s3-bucket dhuan-deploy-<account-id> \
  --s3-prefix dhuan --output-template-file infra/.packaged.yaml --region ap-south-1
aws cloudformation deploy --template-file infra/.packaged.yaml --stack-name dhuan --region ap-south-1 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND --no-fail-on-empty-changeset \
  --parameter-overrides FrontendOrigin=https://main.<app-id>.amplifyapp.com GitHubRepo=HitanshGithub/dhuan \
    ExistingOidcProviderArn=arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com \
    "WaqiToken=$WAQI_TOKEN" \                                           # optional: measured station readings
    AlertEmail=you@example.com                                          # optional: alarm and budget emails (confirm the SNS email once)

# a replay of a past day, built locally from archived fires and winds and published to the data bucket
DHUAN_STORAGE=s3 DHUAN_BUCKET=<DataBucketName> uv run --project backend python -m dhuan.replay --date 2025-11-09 \
  --title "Peak season, 9 November 2025"

# the site
uv run --project backend python infra/deploy_frontend.py --region ap-south-1 --ensure-only   # prints the Amplify URL
cd frontend && VITE_API_BASE=<ApiUrl> npm run build && cd ..
uv run --project backend python infra/deploy_frontend.py --region ap-south-1

# first forecast right away instead of waiting for the top of the hour
aws stepfunctions start-execution --state-machine-arn <StateMachineArn> --region ap-south-1
```

`CodeUri` is set on each function rather than in `Globals` because `aws cloudformation package` only rewrites
resource-level properties.

## Continuous deployment

`.github/workflows/deploy.yml` runs on every push to `main` that touches `backend/`, `frontend/`, `infra/` or
`data/`: tests, Lambda bundle, `sam deploy`, site build with the API URL read from the stack outputs, Amplify
upload, then it starts a forecast run and checks the API answers for Delhi.

GitHub authenticates with OIDC by assuming `dhuan-github-deploy` (defined in the template, scoped to this
repository and this stack's resources). Repository variables needed:

| Variable | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `GitHubDeployRoleArn` output |
| `AWS_OIDC_PROVIDER_ARN` | `arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com` (an account has one provider; this stack reuses it) |
| `AWS_ARTIFACT_BUCKET` | `dhuan-deploy-<account-id>`, the bucket the Lambda package is uploaded to (the deploy role may write only there and to the data bucket) |

GitHub issues OIDC subjects with immutable ids (`repo:owner@123/repo@456:ref:...`); the trust policy accepts
that and the plain `repo:owner/repo:*` form.

## Costs

The hourly run is about 90 seconds of a 3 GB Lambda (roughly $0.005), the frames are about 4 MB per run kept for a
week, CloudFront and S3 requests are pennies, DynamoDB and SNS are on-demand. Bedrock: one Ministral 3 call per
Hindi/Punjabi advisory, a fraction of a paisa. Idle total: well under $5 a month, inside the free tier for most of it.

## Tear down

```bash
aws cloudformation delete-stack --stack-name dhuan --region ap-south-1      # empty the data bucket first
aws amplify delete-app --app-id <app-id> --region ap-south-1
```

SNS topics named `dhuan-sub-*` are created per subscriber at runtime; delete them with `aws sns list-topics` +
`delete-topic` if you tear everything down.
