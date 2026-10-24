FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70

WORKDIR /verifier
COPY --chmod=755 partlab /reference/partlab
COPY parts /reference/parts
COPY test.sh verify.py /tests/
RUN mkdir -p /logs/artifacts /logs/verifier
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
