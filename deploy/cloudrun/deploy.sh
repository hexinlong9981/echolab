#!/usr/bin/env bash
# 公開のデモサーバ（ADR-0013）のイメージを作り、Artifact Registry に送り、Cloud Run に出す。
# setup.sh（最初の 1 回）と、GitHub Actions（.github/workflows/cloudrun.yml）が使う。
#
#   PROJECT_ID=... REGION=us-central1 deploy/cloudrun/deploy.sh [イメージのタグ]
#
# 費用をゼロに保つ設定（Cloud Run の無料枠：毎月 vCPU 18 万秒・メモリ 36 万 GiB 秒・200 万リクエスト）：
# - 最小 0・最大 1 インスタンス（使われないときは止まる。どれだけ呼ばれても 1 台を超えない）
# - CPU はリクエストの処理中だけ（リクエスト単位の課金）。1 vCPU・1 GiB・1 件 120 秒まで（サーバ自身の上限と同じ）
# - 同時に受けるのは 4 件まで（サーバ自身が 1 件ずつ実行し、残りは待たせるか 503 で断る）
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID を指定してください}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-echolab-demo}"
REPOSITORY="${REPOSITORY:-echolab}"
TAG="${1:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
RUNTIME_SA="echolab-demo-run@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE}:${TAG}"

cd "$(dirname "$0")/../.."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet >/dev/null
docker build -f deploy/cloudrun/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"

gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --image="$IMAGE" \
  --service-account="$RUNTIME_SA" \
  --allow-unauthenticated \
  --port=8080 \
  --min-instances=0 --max-instances=1 --concurrency=4 \
  --cpu=1 --memory=1Gi --cpu-throttling --timeout=120 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION" \
  --quiet

gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" \
  --format='value(status.url)'
