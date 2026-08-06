#!/usr/bin/env bash
# One-time GCP resource setup for deploying the backend to Cloud Run (built by
# .github/workflows/deploy-backend.yml). The database stays on Supabase - nothing here
# provisions a database (Cloud SQL has no free tier; Supabase's free Postgres plan is a
# better fit for a personal, infrequently-used app). There is no server-side scheduled
# job either - the background scheduler (services/scheduler.py) is only triggered by the
# frontend calling POST /api/v1/scheduler/run once per login.
#
# Run this once per environment (e.g. once for prod) after `gcloud auth login`
# and `gcloud config set project <PROJECT_ID>`. Safe to re-run - each step
# either no-ops or errors harmlessly if the resource already exists.
#
# Fill in the variables below before running.

set -euo pipefail

PROJECT_ID="REPLACE_WITH_GCP_PROJECT_ID"
REGION="us-central1"
SERVICE_NAME="personal-finance-api"
REPO_NAME="personal-finance"                 # Artifact Registry repo
DEPLOY_SA_NAME="github-deployer"             # service account GitHub Actions assumes to build/deploy
RUNTIME_SA_NAME="backend-runtime"            # service account the Cloud Run service runs as
GITHUB_REPO="ORG/REPO"                       # e.g. octocat/personal-finance

# Supabase connection string (pooled port, e.g. postgresql+asyncpg://...:6543/postgres)
# and the frontend's Firebase Hosting origin - fill in before running.
DATABASE_URL_VALUE="REPLACE_WITH_SUPABASE_DATABASE_URL"
CORS_ORIGIN_REGEX_VALUE='https://.*\.web\.app'

gcloud config set project "$PROJECT_ID"

echo "== Enabling required APIs =="
# iam.googleapis.com + sts.googleapis.com are the two easy ones to forget - the pool and
# provider create fine without them, but the actual STS token exchange
# (google-github-actions/auth's "generate Google Cloud federated token" step, which is
# what every CI run does) fails with an "invalid_target" error at runtime without them.
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  iamcredentials.googleapis.com \
  iam.googleapis.com \
  sts.googleapis.com

echo "== Artifact Registry repo for backend images =="
gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Backend container images" \
  || echo "Repo already exists, skipping."

echo "== Secret Manager secrets =="
# Values are created empty here; add real versions with:
#   echo -n "<value>" | gcloud secrets versions add <secret-name> --data-file=-
for secret in secret-key database-url cors-origins cors-origin-regex; do
  gcloud secrets create "$secret" --replication-policy=automatic \
    || echo "Secret $secret already exists, skipping."
done

echo -n "$DATABASE_URL_VALUE" | gcloud secrets versions add database-url --data-file=-
echo -n "$CORS_ORIGIN_REGEX_VALUE" | gcloud secrets versions add cors-origin-regex --data-file=-
# secret-key: generate and store a random value if this is the first setup
gcloud secrets versions list secret-key --limit=1 --format='value(name)' | grep -q . \
  || python3 -c "import secrets; print(secrets.token_urlsafe(48))" \
     | tr -d '\n' | gcloud secrets versions add secret-key --data-file=-
# cors-origins: bootstrap to a placeholder that matches no real Origin header (Secret
# Manager rejects a genuinely empty payload outright), just so the first `gcloud run
# deploy`'s --set-secrets=...cors-origins:latest... has a version to resolve - only on
# first setup, so a real value set later (once the Firebase Hosting URL is known) isn't
# clobbered by a re-run:
#   echo -n "https://your-project.web.app" | gcloud secrets versions add cors-origins --data-file=-
gcloud secrets versions list cors-origins --limit=1 --format='value(name)' | grep -q . \
  || echo -n "unset" | gcloud secrets versions add cors-origins --data-file=-

echo "== Runtime service account (the Cloud Run service itself runs as this) =="
gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
  --display-name="Backend runtime" \
  || echo "Service account already exists, skipping."

RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None \
  --quiet

echo "== Deploy service account (assumed by GitHub Actions via Workload Identity Federation) =="
gcloud iam service-accounts create "$DEPLOY_SA_NAME" \
  --display-name="GitHub Actions deployer" \
  || echo "Service account already exists, skipping."

DEPLOY_SA_EMAIL="${DEPLOY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# run.admin + artifactregistry.writer to build/push/deploy; secretmanager.secretAccessor
# so the CI migration step can read database-url to run alembic; iam.serviceAccountUser so
# it can deploy *as* RUNTIME_SA_EMAIL.
for role in roles/run.admin roles/artifactregistry.writer roles/secretmanager.secretAccessor roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
    --role="$role" \
    --condition=None \
    --quiet
done

echo "== Workload Identity Federation pool/provider for GitHub Actions =="
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" --display-name="GitHub Actions" \
  || echo "Pool already exists, skipping."

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub OIDC" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  || echo "Provider already exists, skipping."

WIF_POOL_ID=$(gcloud iam workload-identity-pools describe "github-pool" --location="global" --format="value(name)")

gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WIF_POOL_ID}/attribute.repository/${GITHUB_REPO}"

echo ""
echo "Add these as GitHub Actions repo variables/secrets (Settings > Secrets and variables > Actions):"
echo "  GCP_PROJECT_ID              = ${PROJECT_ID}"
echo "  GCP_REGION                  = ${REGION}"
echo "  GCP_WORKLOAD_IDENTITY_PROVIDER = ${WIF_POOL_ID}/providers/github-provider"
echo "  GCP_DEPLOY_SA_EMAIL         = ${DEPLOY_SA_EMAIL}"
echo "  GCP_RUNTIME_SA_EMAIL        = ${RUNTIME_SA_EMAIL}"
echo ""
echo "After the first successful deploy (via .github/workflows/deploy-backend.yml), grab the"
echo "Cloud Run service URL and set it as BACKEND_URL for the frontend build (deploy-frontend.yml)."
