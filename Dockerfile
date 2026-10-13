# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — compila o cpuminer-multi (solo) a partir do repositório oficial.
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS miner-builder

ARG CPUMINER_REF=linux
# Preenchido automaticamente pelo BuildKit (amd64, arm64, ...).
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates build-essential automake autoconf libtool pkg-config \
        libcurl4-openssl-dev libssl-dev zlib1g-dev libjansson-dev libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${CPUMINER_REF}" \
        https://github.com/tpruvot/cpuminer-multi.git /src

WORKDIR /src

# x86/x86_64 aproveitam as rotinas de assembly (SHA-NI/AVX); no ARM o assembly
# do projeto usa instruções de 32 bits, então compilamos em C puro.
RUN ./autogen.sh \
    && if [ "${TARGETARCH}" = "arm64" ] || [ "${TARGETARCH}" = "arm" ]; then \
         CONFIGURE_FLAGS="--disable-assembly"; \
       else \
         CONFIGURE_FLAGS=""; \
       fi \
    && ./configure CFLAGS="-O3" ${CONFIGURE_FLAGS} \
    && make -j"$(nproc)" \
    && strip minerd \&& strip minerd \ strip cpuminer \
    && install -m 0755 cpuminer /usr/local/bin/cpuminer

# ---------------------------------------------------------------------------
# Stage 2 — runtime enxuto: Python + FastAPI + binário do cpuminer.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Bibliotecas de runtime exigidas pelo cpuminer + gosu (drop de privilégios).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcurl4 libssl3 zlib1g libjansson4 libgmp10 gosu ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=miner-builder /usr/local/bin/cpuminer /usr/local/bin/cpuminer

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin miner \
    && mkdir -p /app/data \
    && chown -R miner:miner /app

ENV LOTTERY_DATA_DIR=/app/data

VOLUME ["/app/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
