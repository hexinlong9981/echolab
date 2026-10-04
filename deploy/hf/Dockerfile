# 公開のデモサーバ（ADR-0013）。Hugging Face Spaces（Docker・無料の CPU）で動かす。
# 台本の LLM だけを使い、計算サービスは実物（calc-engine の jar・OCR・住宅ローン・無職転生）。
# ビルドの文脈はリポジトリ直下（CI は deploy/hf/Dockerfile をリポジトリ直下に置いて Space に送る）。
#
#   docker build -f deploy/hf/Dockerfile -t echolab-public .
#   docker run --rm -p 7860:7860 echolab-public

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

# Hugging Face Spaces の推奨どおり、UID 1000 の一般ユーザで動かす
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
EXPOSE 7860
CMD ["python", "-m", "servers.web_api", "--public", "--host", "0.0.0.0", "--port", "7860"]
