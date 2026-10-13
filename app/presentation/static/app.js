"use strict";

/**
 * Dashboard do btc-lottery-miner — JavaScript puro (sem dependências).
 * Fala com a API REST (/api/*) e assina os logs via Server-Sent Events.
 */

const $ = (id) => document.getElementById(id);

const state = {
  words: [],
  configured: false,
  logCount: 0,
};

const MAX_LOG_LINES = 800;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 204) return null;
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error((body && body.detail) || `Erro HTTP ${response.status}`);
  }
  return body;
}

function toast(message, isError = false) {
  const element = $("toast");
  element.textContent = message;
  element.classList.toggle("error", isError);
  element.hidden = false;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    element.hidden = true;
  }, 5000);
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return "—";
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

function formatTime(epochSeconds) {
  if (!epochSeconds) return "—";
  return new Date(epochSeconds * 1000).toLocaleString("pt-BR");
}

/* ---------------------------------------------------------------- carteira */

async function loadWallet() {
  const wallet = await api("/api/wallet");
  state.configured = wallet.configured;
  const badge = $("wallet-badge");
  if (wallet.configured) {
    badge.textContent = wallet.address.slice(0, 14) + "…";
    $("current-address").textContent = wallet.address;
    $("wallet-setup").hidden = true;
    $("dashboard").hidden = false;
    await loadSettings();
    await refreshStatus();
    await refreshPool();
    await loadHistory();
    connectLogs();
  } else {
    badge.textContent = "sem carteira";
    $("wallet-setup").hidden = false;
    $("dashboard").hidden = true;
  }
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((other) => other.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.tab;
      $("tab-generate").hidden = target !== "generate";
      $("tab-import").hidden = target !== "import";
    });
  });
}

function renderSeed(words, address) {
  state.words = words;
  $("derived-address").textContent = address;
  const list = $("seed-words");
  list.innerHTML = "";
  words.forEach((word) => {
    const item = document.createElement("li");
    item.textContent = word;
    list.appendChild(item);
  });
  $("seed-area").hidden = false;
}

function setupWalletForms() {
  $("btn-generate").addEventListener("click", async () => {
    try {
      const generated = await api("/api/wallet/generate", {
        method: "POST",
        body: JSON.stringify({ words: 12 }),
      });
      renderSeed(generated.mnemonic, generated.address);
      toast("Seed gerada. Anote as palavras e confirme.");
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("confirm-saved").addEventListener("change", (event) => {
    $("btn-confirm").disabled = !event.target.checked;
  });

  $("store-seed").addEventListener("change", (event) => {
    $("seed-passphrase").hidden = !event.target.checked;
  });

  $("btn-confirm").addEventListener("click", async () => {
    try {
      await api("/api/wallet/confirm", {
        method: "POST",
        body: JSON.stringify({
          mnemonic: state.words.join(" "),
          store_seed: $("store-seed").checked,
          passphrase: $("seed-passphrase").value || null,
        }),
      });
      toast("Carteira configurada!");
      await loadWallet();
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("import-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/wallet/import/address", {
        method: "POST",
        body: JSON.stringify({ address: $("import-address").value.trim() }),
      });
      toast("Endereço importado!");
      await loadWallet();
    } catch (error) {
      toast(error.message, true);
    }
  });
}

/* -------------------------------------------------------------- mineração */

async function loadSettings() {
  const settings = await api("/api/settings");
  $("threads").value = settings.threads;
  $("threads-value").textContent = settings.threads;
  $("worker").value = settings.worker;
  $("pool-url").value = settings.pool_url;
}

function renderStatus(status) {
  $("stat-state").textContent = status.state;
  $("stat-hashrate").textContent = status.hashrate > 0 ? status.hashrate_human : "—";
  $("stat-uptime").textContent = formatDuration(status.uptime_seconds);
  $("stat-shares").textContent = `${status.shares.accepted}/${status.shares.accepted + status.shares.rejected}`;
  $("threads-value").textContent = status.threads || $("threads").value;

  const running = status.state === "running" || status.state === "starting";
  $("btn-start").disabled = running;
  $("btn-stop").disabled = !running;

  const errorBox = $("miner-error");
  if (status.last_error) {
    errorBox.textContent = status.last_error;
    errorBox.hidden = false;
  } else {
    errorBox.hidden = true;
  }
}

async function refreshStatus() {
  try {
    renderStatus(await api("/api/miner/status"));
  } catch (error) {
    /* silencioso: o servidor pode estar reiniciando */
  }
}

function renderPool(stats) {
  if (!stats.found) {
    $("pool-note").textContent = "Endereço ainda não visto pela pool (nenhum share enviado).";
    return;
  }
  $("pool-workers").textContent = stats.workers ?? "—";
  $("pool-shares").textContent = stats.shares ?? "—";
  const oneMinute = stats.hashrates && (stats.hashrates.hashrate1m ?? stats.hashrates.hashrate5m);
  $("pool-hashrate").textContent = oneMinute ? humanRate(oneMinute) : "—";
  $("pool-best").textContent = stats.best_share ? formatNumber(stats.best_share) : "—";
  $("pool-note").textContent = `Atualizado em ${formatTime(stats.fetched_at)}`;
}

function humanRate(value) {
  const units = ["H/s", "kH/s", "MH/s", "GH/s", "TH/s", "PH/s"];
  let index = 0;
  let current = value;
  while (current >= 1000 && index < units.length - 1) {
    current /= 1000;
    index += 1;
  }
  return `${current.toFixed(2)} ${units[index]}`;
}

function formatNumber(value) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

async function refreshPool() {
  try {
    renderPool(await api("/api/pool/stats"));
  } catch (error) {
    $("pool-note").textContent = "Não foi possível consultar a pool agora.";
  }
}

function setupMinerControls() {
  $("btn-start").addEventListener("click", async () => {
    try {
      const threads = Number($("threads").value);
      renderStatus(await api("/api/miner/start", {
        method: "POST",
        body: JSON.stringify({ threads }),
      }));
      toast("Mineração iniciada.");
      await loadHistory();
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("btn-stop").addEventListener("click", async () => {
    try {
      renderStatus(await api("/api/miner/stop", { method: "POST" }));
      toast("Mineração parada.");
      await loadHistory();
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("threads").addEventListener("input", (event) => {
    $("threads-value").textContent = event.target.value;
  });

  $("threads").addEventListener("change", async (event) => {
    try {
      await api("/api/settings", {
        method: "PUT",
        body: JSON.stringify({ threads: Number(event.target.value) }),
      });
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("settings-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/settings", {
        method: "PUT",
        body: JSON.stringify({
          worker: $("worker").value.trim(),
          pool_url: $("pool-url").value.trim(),
        }),
      });
      toast("Configurações salvas.");
    } catch (error) {
      toast(error.message, true);
    }
  });
}

/* ------------------------------------------------------------------ logs */

function appendLog(entry) {
  const container = $("logs");
  const line = document.createElement("div");
  if (entry.stream === "stderr") line.className = "err";
  if (entry.stream === "system") line.className = "sys";
  const time = new Date(entry.timestamp * 1000).toLocaleTimeString("pt-BR");
  line.textContent = `[${time}] ${entry.message}`;
  container.appendChild(line);

  state.logCount += 1;
  if (state.logCount > MAX_LOG_LINES) {
    container.removeChild(container.firstChild);
    state.logCount -= 1;
  }
  container.scrollTop = container.scrollHeight;
}

function connectLogs() {
  const source = new EventSource("/api/miner/logs");
  source.onmessage = (event) => {
    try {
      appendLog(JSON.parse(event.data));
    } catch (error) {
      /* ignora mensagens malformadas */
    }
  };
  source.onerror = () => {
    /* o EventSource reconecta automaticamente */
  };
}

async function loadHistory() {
  try {
    const events = await api("/api/miner/history?limit=25");
    const body = $("history-body");
    body.innerHTML = "";
    events.forEach((event) => {
      const row = document.createElement("tr");
      row.innerHTML = `<td>${formatTime(event.created_at)}</td><td>${event.kind}</td><td>${JSON.stringify(event.detail)}</td>`;
      body.appendChild(row);
    });
  } catch (error) {
    /* silencioso */
  }
}

function setupLogsControls() {
  $("btn-clear-logs").addEventListener("click", () => {
    $("logs").innerHTML = "";
    state.logCount = 0;
  });
}

/* ------------------------------------------------------------------ start */

async function init() {
  setupTabs();
  setupWalletForms();
  setupMinerControls();
  setupLogsControls();
  try {
    await loadWallet();
  } catch (error) {
    toast(error.message, true);
  }
  setInterval(refreshStatus, 3000);
  setInterval(refreshPool, 30000);
}

document.addEventListener("DOMContentLoaded", init);
