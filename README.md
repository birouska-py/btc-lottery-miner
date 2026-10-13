# btc-lottery-miner ⛏️

Minerador de **loteria solo de Bitcoin via CPU** — backend e dashboard em um **único container Docker**, com **persistência local** (volume Docker) e **banco SQLite criptografado**.

> "Loteria solo" = você mina sozinho (via [`solo.ckpool.org`](https://solo.ckpool.org)).
> Se um bloco for encontrado, a recompensa inteira (subsídio + taxas) vai direto para o
> seu endereço. A chance é baixíssima, mas o custo é só a eletricidade da CPU.

---

## ✨ Recursos

- **Carteira 100% offline**: geração BIP-39 (12 palavras) e derivação **BIP-84 Native SegWit** (`bc1q...`, caminho `m/84'/0'/0'/0/0`) com `mnemonic` + `bip_utils`.
- **Seed só aparece uma vez**: no setup a UI mostra as 12 palavras; depois disso a app guarda apenas o **endereço público** e um **hash de validação**. Opcionalmente a seed pode ser guardada **cifrada** (AES-GCM) com uma senha do usuário.
- **Banco criptografado em repouso**: SQLite em `/app/data/app.db` com segredos cifrados por **Argon2id → AES-256-GCM** (biblioteca `cryptography`).
- **Controle do minerador**: start/stop assíncrono do `cpuminer` (algoritmo `sha256d`), ajuste de **threads** e **streaming de logs em tempo real** (SSE).
- **Monitoramento da pool**: consulta periódica a `https://solo.ckpool.org/users/<endereço>` (shares, workers, hashrate, melhor share) com cache.
- **Dashboard web** responsivo em modo escuro (HTML/CSS/JS puro, sem build de frontend).
- **Arquitetura DDD**: domínio puro, portas/adaptadores, injeção de dependências e testes com *fakes* em memória.

---

## 🐳 Subir com Docker (recomendado)

```bash
# 1. build + start (persiste em ./data)
docker compose up -d --build

# 2. abra o dashboard
xdg-open http://localhost:8080   # ou http://<ip-da-maquina>:8080
```

O volume `./data:/app/data` guarda o banco criptografado. **Pare, recrie ou atualize o
container sem perder configurações nem estado:**

```bash
docker compose down            # para (mantém ./data)
docker compose up -d --build   # reconstrói/atualiza
```

> **Sem clonar/buildar?** Use a imagem publicada:
>
> ```bash
> docker run -d --name btc-lottery-miner -p 8080:8080 \
>   -v "$PWD/data:/app/data" birouskapy/btc-lottery-miner:latest
> ```

> **Rodar mais de uma instância?** O SQLite não suporta escrita concorrente confiável no
> mesmo arquivo. Para escalar, use **um volume por instância**:
>
> ```bash
> mkdir -p data-01 data-02
> docker run -d --name miner-01 -p 8080:8080 -v "$PWD/data-01:/app/data" btc-lottery-miner:latest
> docker run -d --name miner-02 -p 8081:8080 -v "$PWD/data-02:/app/data" btc-lottery-miner:latest
> ```

---

## 🚀 Uso

1. **Configurar carteira**
   - *Gerar nova*: clique em **Gerar carteira**, anote as 12 palavras, marque a confirmação e finalize.
     (Opcional: marque *guardar a seed criptografada* e informe uma senha.)
   - *Importar endereço*: se você já tem um `bc1q...`, basta colá-lo — a mineração só precisa do endereço público.
2. **Iniciar mineração**: escolha as **threads** (nº de núcleos) e clique em **Iniciar**.
3. Acompanhe o **console de logs**, o **status** (hashrate/shares/uptime) e as **estatísticas da pool**.
   A **recompensa** cai no endereço configurado caso um bloco seja encontrado.

> ⚠️ A CPU é muito lenta para SHA-256d. Este projeto é educativo/experimental ("loteria"):
> a probabilidade é ínfima e o consumo de energia é real.

---

## 🔐 Segurança

| Item | Como é tratado |
| --- | --- |
| Seed phrase | Nunca persistida em claro. Exibida uma única vez no setup. |
| Seed opcional no servidor | Cifrada com **AES-256-GCM**; chave derivada da senha do usuário via **Argon2id** (salt aleatório por token). |
| Validação | Guarda-se um **hash SHA-256** da seed (impressão digital), não a seed. |
| Endereço | É público por natureza; gravado em claro para exibição. |
| Imagem Docker | **Sem segredos** na imagem: `.dockerignore` bloqueia `data/`, `.env` e `*.db`. O container roda como usuário **não-root** (`gosu`, uid 1000). |
| Exposição | O dashboard não tem autenticação — **não exponha à internet** sem um proxy com TLS/auth. |

Token de cifragem (base64 url-safe):

```
[ versão 1B ][ salt 16B ][ nonce 12B ][ ciphertext + tag ]
```

---

## 🏗️ Arquitetura (DDD)

```
app/
├── main.py                     # entrypoint FastAPI (uvicorn app.main:app)
├── config.py                   # Settings (env, prefixo LOTTERY_)
├── container.py                # composition root (wiring)
├── domain/                     # regras puras (sem I/O)
│   ├── wallet.py               #   Mnemonic, WalletAddress, Fingerprint, DerivationPath, Wallet
│   ├── mining.py               #   MiningConfig, MinerStatus, MinerState, HashRate, ShareStats
│   ├── stats.py                #   PoolStats
│   ├── history.py              #   HistoryEvent
│   └── errors.py               #   hierarquia de erros de domínio
├── application/                # casos de uso + portas (interfaces)
│   ├── ports.py                #   Protocol: repositórios, deriver, cipher, processo, cliente
│   ├── models.py               #   AppSettings, GeneratedWallet
│   ├── wallet_service.py       #   gerar/importar/validar/revelar seed
│   ├── settings_service.py     #   threads, worker, pool
│   ├── mining_service.py       #   start/stop/status/histórico/logs
│   └── pool_service.py         #   estatísticas da pool (cache)
├── infrastructure/             # adaptadores concretos
│   ├── crypto.py               #   Argon2id + AES-GCM (key derivation + PassphraseCipher)
│   ├── database.py             #   SQLite + migrações (PRAGMA user_version)
│   ├── repositories.py         #   repositórios SQLite
│   ├── wallet_deriver.py       #   BIP-39 / BIP-84 (bip_utils)
│   ├── miner_process.py        #   subprocesso cpuminer + streaming
│   └── pool_client.py          #   cliente HTTP da CKPool
└── presentation/               # borda HTTP + UI
    ├── api.py                  #   REST + SSE
    ├── schemas.py              #   modelos Pydantic
    ├── deps.py                 #   injeção de dependências
    ├── templates/index.html    #   dashboard
    └── static/                 #   styles.css + app.js
```

### API

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/api/health` | Healthcheck (usado pelo Docker). |
| GET | `/api/wallet` | Status da carteira. |
| POST | `/api/wallet/generate` | Gera seed (`{"words": 12}`). |
| POST | `/api/wallet/confirm` | Persiste a carteira (`{"mnemonic", "store_seed", "passphrase"}`). |
| POST | `/api/wallet/import/address` | Importa um `bc1q...`. |
| POST | `/api/wallet/reveal` | Revela a seed armazenada (com senha). |
| POST | `/api/wallet/verify` | Confere uma seed com a impressão digital. |
| DELETE | `/api/wallet` | Remove carteira e seed armazenada. |
| GET/PUT | `/api/settings` | Preferências (threads/worker/pool). |
| POST | `/api/miner/start` | Inicia (`{"threads": n}` opcional). |
| POST | `/api/miner/stop` | Para a mineração. |
| GET | `/api/miner/status` | Estado atual. |
| GET | `/api/miner/history` | Histórico de execução. |
| GET | `/api/miner/logs` | **SSE** com logs ao vivo. |
| GET | `/api/pool/stats` | Estatísticas da pool (cache; `?refresh=true` força). |

Documentação interativa: `http://localhost:8080/docs`.

---

## 💻 Desenvolvimento local

Requer Python ≥ 3.12 e [`uv`](https://docs.astral.sh/uv/).

```bash
make install      # uv sync
make run          # uvicorn --reload em http://localhost:8080
```

Qualidade (o que o CI roda):

```bash
make lint         # ruff check
make typecheck    # mypy --strict
make test         # pytest + cobertura (coverage.xml)
make check        # lint + typecheck + test
make sonar        # SonarQube (SONAR_TOKEN=... make sonar)
```

> Para a mineração local sem Docker, instale o `cpuminer` e garanta que ele esteja no `PATH`
> (ou defina `LOTTERY_CPUMINER_BIN=/caminho/para/cpuminer`).

### Variáveis de ambiente

Todas usam o prefixo `LOTTERY_` (veja [`.env.example`](.env.example)):

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `LOTTERY_DATA_DIR` | `data` | Diretório do banco (volume). |
| `LOTTERY_HOST` / `LOTTERY_PORT` | `0.0.0.0` / `8080` | Bind do servidor. |
| `LOTTERY_DEFAULT_POOL_URL` | `stratum+tcp://solo.ckpool.org:3333` | Pool padrão. |
| `LOTTERY_CKPOOL_BASE_URL` | `https://solo.ckpool.org` | Base das estatísticas. |
| `LOTTERY_DEFAULT_THREADS` / `LOTTERY_MAX_THREADS` | `1` / `256` | Limites de threads. |
| `LOTTERY_CPUMINER_BIN` | `cpuminer` | Caminho do binário. |

---

## 🐋 Publicar imagem

A imagem oficial está publicada em **`birouskapy/btc-lottery-miner`**
(Docker Hub) com as tags `0.1.0` e `latest`.

### Docker Hub

```bash
docker build -t birouskapy/btc-lottery-miner:0.1.0 .
docker tag  birouskapy/btc-lottery-miner:0.1.0 birouskapy/btc-lottery-miner:latest
docker login
docker push birouskapy/btc-lottery-miner:0.1.0
docker push birouskapy/btc-lottery-miner:latest
```

### Multi-arch (amd64 + arm64)

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t birouskapy/btc-lottery-miner:latest --push .
```

> A imagem **não contém segredos**. Publicá-la não expõe a seed nem o endereço — isso vive
> apenas no volume `./data` da sua máquina.

---

## 💾 Backup e restore

Tudo que importa está em `./data` (`app.db`). Com o container parado para consistência:

```bash
# backup
docker compose down
tar -czf btc-lottery-miner-backup-$(date +%Y%m%d).tar.gz data/
docker compose up -d

# restore
docker compose down
tar -xzf btc-lottery-miner-backup-YYYYMMDD.tar.gz
docker compose up -d
```

> Guarde o backup em local seguro: se você optou por armazenar a seed cifrada, **a senha não
> vai no backup** — sem ela a seed é irrecuperável (por design).

---

## 🧪 Testes

- Domínio: validações de seed/endereço/configuração e formatação de hashrate.
- Crypto: ida-e-volta, detecção de adulteração e senha errada.
- Infraestrutura: repositórios SQLite (arquivo temporário), derivação BIP-84 com vetor oficial, parsing do cpuminer e cliente da pool (via `respx`).
- Aplicação: serviços com *fakes* em memória.
- Apresentação: endpoints REST e SSE com `httpx.ASGITransport`.

Vetor BIP-84 usado nos testes:
`abandon abandon … about` → `bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu`.

---

## 📄 Licença

[MIT](LICENSE).
