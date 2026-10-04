# 公開のデモサーバ（ADR-0013）。Google Cloud Run（無料枠の範囲）で動かす。
# 台本の LLM だけを使い、計算サービスは実物（calc-engine の jar・OCR・住宅ローン・無職転生）。
# ビルドの文脈はリポジトリ直下。イメージは小さく保つ（Artifact Registry の無料枠は 0.5 GB）。
#
#   docker build -f deploy/cloudrun/Dockerfile -t echolab-demo .
#   docker run --rm -p 8080:8080 echolab-demo        # Cloud Run と同じく PORT=8080

# --- calc-engine の jar を作る ---------------------------------------------------
FROM eclipse-temurin:21-jdk AS jar
WORKDIR /src/services/calc-engine
COPY services/calc-engine/ ./
RUN ./gradlew --no-daemon -q bootJar -x test

# --- 実行 ------------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JAVA_HOME=/opt/java/openjdk \
    PATH=/opt/java/openjdk/bin:$PATH
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-jpn \
 && rm -rf /var/lib/apt/lists/*
COPY --from=eclipse-temurin:21-jre /opt/java/openjdk /opt/java/openjdk

# root ではない一般ユーザで動かす
RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user core/ core/
COPY --chown=user config/ config/
COPY --chown=user domains/ domains/
COPY --chown=user servers/ servers/
COPY --chown=user evals/redteam/screenshots/ evals/redteam/screenshots/
COPY --chown=user --from=jar /src/services/calc-engine/build/libs/calc-engine-mcp.jar \
     services/calc-engine/build/libs/calc-engine-mcp.jar
USER user
# Cloud Run は待ち受けるポートを環境変数 PORT で渡す（既定 8080）。--port を省くとそれを使う
ENV PORT=8080
EXPOSE 8080
CMD ["python", "-m", "servers.web_api", "--public", "--host", "0.0.0.0"]
