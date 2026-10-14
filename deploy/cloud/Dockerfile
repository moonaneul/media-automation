# Environment probe only: no HTTP server, church data, or cloud credentials.
FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-impress libreoffice-writer poppler-utils ffmpeg \
    fontconfig fonts-noto-cjk fonts-nanum \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[cloud]" && useradd --uid 10001 --create-home media
USER 10001
ENTRYPOINT ["python", "-m", "media_automation.cloud.runtime_check"]
