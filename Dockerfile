FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

RUN pip install --no-cache-dir -e ".[all]"

# ── Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/pyclaw /usr/local/bin/pyclaw
COPY --from=builder /app /app

EXPOSE 18789 18790

VOLUME ["/root/.pyclaw"]

ENTRYPOINT ["pyclaw"]
CMD ["gateway"]
