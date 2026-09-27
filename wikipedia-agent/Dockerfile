FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    WORK_DIR=/data \
    SKILLS_DIR=/app/skills

WORKDIR /app

# fully pinned lock (see requirements.in); explicit pins let pip install the OpenTelemetry *b0 releases
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY skills ./skills
COPY app ./app

RUN useradd --uid 10001 --create-home agent && mkdir -p /data && chown agent /data
USER 10001
VOLUME /data
EXPOSE 8080

# Standalone API + web UI. For kagent (BYO Agent) the command is `uvicorn app.kagent_main:app ...`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
