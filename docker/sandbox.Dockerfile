# Minimal image for running a target repo's tests in isolation.
# Built once with network access; containers then run with --network none.
FROM python:3.12-slim

RUN pip install --no-cache-dir "pytest==8.*" \
    && useradd --create-home --uid 10001 sandbox

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER sandbox
WORKDIR /work
