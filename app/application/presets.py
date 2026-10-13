"""Presets de pool exibidos na interface (seletor de pool).

O painel de **estatísticas** do app consulta a API pública do CKPool; ao usar outra
pool a mineração continua normal, mas o painel de stats pode não ter dados.
"""

from __future__ import annotations

from app.application.models import PoolPreset

POOL_PRESETS: tuple[PoolPreset, ...] = (
    PoolPreset("CKPool solo (global)", "stratum+tcp://solo.ckpool.org:3333"),
    PoolPreset("CKPool solo — Europa", "stratum+tcp://eusolo.ckpool.org:3333"),
    PoolPreset("CKPool solo — EUA leste", "stratum+tcp://uesolo.ckpool.org:3333"),
    PoolPreset("CKPool solo — EUA oeste", "stratum+tcp://uwsolo.ckpool.org:3333"),
    PoolPreset("CKPool solo — Singapura", "stratum+tcp://sgsolo.ckpool.org:3333"),
    PoolPreset("CKPool solo — Austrália", "stratum+tcp://ausolo.ckpool.org:3333"),
    PoolPreset("Mineshop solo (Europa)", "stratum+tcp://solo.mineshop.eu:3333"),
    PoolPreset("SoloPool.com", "stratum+tcp://stratum.solopool.com:3333"),
    PoolPreset("SoloPool.org", "stratum+tcp://btc.solopool.org:3333"),
)
