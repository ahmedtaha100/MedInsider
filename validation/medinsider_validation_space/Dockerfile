FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /app
RUN apt-get update \
    && curl_version="$(apt-cache policy curl | awk '/Candidate:/ {print $2}')" \
    && apt-get install -y --no-install-recommends "curl=${curl_version}" \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
RUN useradd --create-home --shell /bin/sh appuser \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:7860/_stcore/health || exit 1
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
