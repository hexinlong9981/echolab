#!/usr/bin/env bash
# 公開のデモサーバ（ADR-0013）を Google Cloud Run に置くための最初の 1 回の準備。何度実行してもよい。
#
#   deploy/cloudrun/setup.sh <PROJECT_ID> [REGION]      # REGION の既定は us-central1
#
# 前提：gcloud にログイン済み（利用者が自分の端末で `gcloud auth login`）、プロジェクトに
# 請求先アカウントがつながっている、docker と gh が使える。
#
# 作るもの：
# - API の有効化、Artifact Registry のリポジトリ（古いイメージを自動で消すクリーンアップ方針つき）
# - 実行用のサービスアカウント（権限なし）と、GitHub Actions 用のデプロイ用サービスアカウント
# - Workload Identity 連携（鍵ファイルなし。hexinlong9981/echolab の main からだけ使える）
# - 予算アラート（1 USD。50%・90%・100% でメール。費用が出始めたらすぐ気づくため）
# - 最初のデプロイと、GitHub のリポジトリ変数（GCP_*・LIVE_API_URL）の登録
#
# us-central1 を既定にするのは、無料枠の「北米からの外向き通信 毎月 1 GB」の対象にするため。
set -euo pipefail

PROJECT_ID="${1:?使い方: setup.sh <PROJECT_ID> [REGION]}"
REGION="${2:-us-central1}"
GITHUB_REPO="hexinlong9981/echolab"
REPOSITORY="echolab"
POOL="github"
PROVIDER="github-oidc"
RUNTIME_SA_NAME="echolab-demo-run"
DEPLOYER_SA_NAME="echolab-deployer"
RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOYER_SA="${DEPLOYER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
HERE="$(cd "$(dirname "$0")" && pwd)"

say() { printf '\n== %s\n' "$*"; }

gcloud config set project "$PROJECT_ID" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
BILLING="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingAccountName)' | sed 's#billingAccounts/##')"
if [ -z "$BILLING" ]; then
  echo "エラー: プロジェクト $PROJECT_ID に請求先アカウントがつながっていません" >&2
  exit 1
fi

say "API を有効にする"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com cloudresourcemanager.googleapis.com \
  billingbudgets.googleapis.com cloudbilling.googleapis.com

say "Artifact Registry（無料枠 0.5 GB。最新の 1 つだけ残す）"
gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker \
    --location="$REGION" --description="EchoLab の公開デモサーバ（ADR-0013）"
gcloud artifacts repositories set-cleanup-policies "$REPOSITORY" --location="$REGION" \
  --policy="$HERE/cleanup-policy.json" --quiet  # --dry-run を付けないので実際に消す

say "サービスアカウント"
gcloud iam service-accounts describe "$RUNTIME_SA" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "$RUNTIME_SA_NAME" --display-name="EchoLab demo (runtime, Vertex AI caller)"
gcloud iam service-accounts describe "$DEPLOYER_SA" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "$DEPLOYER_SA_NAME" --display-name="EchoLab demo deployer (GitHub Actions)"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/aiplatform.user" --condition=None --quiet >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/run.admin" --condition=None --quiet >/dev/null
gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" --location="$REGION" \
  --member="serviceAccount:$DEPLOYER_SA" --role="roles/artifactregistry.writer" --quiet >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --member="serviceAccount:$DEPLOYER_SA" --role="roles/iam.serviceAccountUser" --quiet >/dev/null

say "Workload Identity 連携（GitHub Actions から鍵なしでデプロイ）"
gcloud iam workload-identity-pools describe "$POOL" --location=global >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools create "$POOL" --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe "$PROVIDER" --location=global \
  --workload-identity-pool="$POOL" >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --location=global \
    --workload-identity-pool="$POOL" --display-name="GitHub OIDC" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}' && assertion.ref=='refs/heads/main'"
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${GITHUB_REPO}" \
  --quiet >/dev/null

# 予算の通貨は請求先アカウントの通貨に合わせる（日本円のアカウントは 150 JPY ≒ 1 USD）。
# 無料トライアルのクレジットで差し引かれた分も「費用」として数え、早めに気づけるようにする。
CURRENCY="$(gcloud billing accounts describe "$BILLING" --format='value(currencyCode)')"
case "$CURRENCY" in
  JPY) AMOUNT=150JPY ;;
  *) AMOUNT="1${CURRENCY:-USD}" ;;
esac
say "予算アラート（$AMOUNT）"
if ! gcloud billing budgets list --billing-account="$BILLING" --format='value(displayName)' |
  grep -qx "EchoLab demo"; then
  gcloud billing budgets create --billing-account="$BILLING" --display-name="EchoLab demo" \
    --budget-amount="$AMOUNT" --credit-types-treatment=exclude-all-credits \
    --filter-projects="projects/${PROJECT_ID}" \
    --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0
fi

say "最初のデプロイ"
URL="$(PROJECT_ID="$PROJECT_ID" REGION="$REGION" "$HERE/deploy.sh" | tail -n 1)"
echo "$URL"
curl -fsS "$URL/api/health" && echo

say "GitHub のリポジトリ変数（Actions がデプロイに使う。秘密の値は無い）"
gh variable set GCP_PROJECT_ID -R "$GITHUB_REPO" --body "$PROJECT_ID"
gh variable set GCP_REGION -R "$GITHUB_REPO" --body "$REGION"
gh variable set GCP_WIF_PROVIDER -R "$GITHUB_REPO" --body "$WIF_PROVIDER"
gh variable set GCP_SERVICE_ACCOUNT -R "$GITHUB_REPO" --body "$DEPLOYER_SA"
gh variable set LIVE_API_URL -R "$GITHUB_REPO" --body "$URL"

say "完了"
echo "公開のデモサーバ: $URL"
echo "次に GitHub の web ワークフローを実行すると、リプレイに「サーバで実際に実行」が出ます：gh workflow run web.yml -R $GITHUB_REPO"
