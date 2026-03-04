FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/

# Use [docker] extra to avoid llamacpp/mlx build failures (need CMake/Apple libs)
RUN pip install --no-cache-dir ".[docker]"

# ── Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/pyclaw /usr/local/bin/pyclaw

EXPOSE 18789 18790

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD pyclaw health || exit 1

VOLUME ["/root/.pyclaw"]

ENTRYPOINT ["pyclaw"]
CMD ["gateway"]
