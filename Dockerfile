# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — compila o cpuminer-multi (branch "linux") a partir do repositório
# oficial, com o commit FIXO para um build reproduzível.
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS miner-builder

# Commit fixo do tpruvot/cpuminer-multi (branch "master") para build reproduzível.
ARG CPUMINER_REF=4b5c6dafb677191e968cfd12068923068a7bdf51

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates build-essential automake autoconf libtool pkg-config \
        libcurl4-openssl-dev libssl-dev zlib1g-dev libjansson-dev libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git init /src \
    && cd /src \
    && git remote add origin https://github.com/tpruvot/cpuminer-multi.git \
    && git fetch --depth 1 origin "${CPUMINER_REF}" \
    && git checkout FETCH_HEAD

WORKDIR /src

RUN ./autogen.sh \
    && ./configure CFLAGS="-O3" \
    && make -j"$(nproc)" \
    && strip minerd \
    && install -m 0755 minerd /usr/local/bin/cpuminer

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
