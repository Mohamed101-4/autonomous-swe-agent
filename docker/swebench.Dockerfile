# Test environment for SWE-bench instances (built once per environment, with network).
# The repo itself is NOT installed: it is mounted read-only at /work and imported
# via PYTHONPATH, and containers run with --network none like the main sandbox.
ARG PYTHON=3.9
FROM python:${PYTHON}-slim

ARG PACKAGES
RUN pip install --no-cache-dir ${PACKAGES} \
    && useradd --create-home --uid 10001 sandbox

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER sandbox
WORKDIR /work
