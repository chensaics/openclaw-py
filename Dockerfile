ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/

# [docker] extra excludes llamacpp/mlx (need C++ compilers) and
# whatsapp/neonize (protobuf version conflict with google-generativeai)
RUN pip install --no-cache-dir ".[docker]"

# ── Runtime ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages — use python -c to discover the site-packages path
# so upgrading PYTHON_VERSION doesn't break the build.
COPY --from=builder /usr/local/lib/ /usr/local/lib/
COPY --from=builder /usr/local/bin/pyclaw /usr/local/bin/pyclaw

EXPOSE 18789 18790

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD pyclaw health || exit 1

VOLUME ["/root/.pyclaw"]

ENTRYPOINT ["pyclaw"]
CMD ["gateway"]
