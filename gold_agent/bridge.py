"""Pont vers TradingView Desktop via la CLI claudeverstradingview (CDP).

Chaque appel lance un process node qui se reconnecte au CDP. C'est lent
(~2-4s) mais fiable. On regroupe donc les lectures par timeframe.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path(os.environ.get("TV_BRIDGE_REPO", Path.home() / "claudeverstradingview"))
CLI = REPO / "src" / "cli" / "index.js"
TV_APP = "/Applications/TradingView.app/Contents/MacOS/TradingView"
CDP_PORT = 9222


class BridgeError(RuntimeError):
    pass


def _run(args: list[str], timeout: int = 90) -> dict:
    if not CLI.exists():
        raise BridgeError(f"CLI introuvable: {CLI}. Le repo est-il bien cloné ?")
    proc = subprocess.run(
        ["node", str(CLI), *args],
        capture_output=True, text=True, timeout=timeout, cwd=str(REPO),
    )
    out = proc.stdout.strip()
    if not out:
        raise BridgeError(f"Aucune sortie pour {' '.join(args)}. stderr: {proc.stderr.strip()[:300]}")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise BridgeError(f"Sortie non-JSON pour {' '.join(args)}: {out[:300]}")
    if isinstance(data, dict) and data.get("success") is False:
        raise BridgeError(f"{' '.join(args)} a échoué: {data.get('error')}")
    return data


def status() -> dict:
    return _run(["status"], timeout=60)


def is_connected() -> bool:
    try:
        return bool(status().get("cdp_connected"))
    except Exception:
        return False


def ensure_tradingview(wait: int = 30) -> bool:
    """Relance TradingView en mode debug si le CDP ne répond pas.

    TVD_DEBUGMODE=true est OBLIGATOIRE sur TradingView Desktop v3.x : sans
    cette variable l'app ouvre bien le port CDP mais refuse toute connexion.
    """
    if is_connected():
        return True
    if not Path(TV_APP).exists():
        raise BridgeError(f"TradingView Desktop introuvable: {TV_APP}")
    subprocess.run(["pkill", "-f", "TradingView"], capture_output=True)
    time.sleep(2)
    env = {**os.environ, "TVD_DEBUGMODE": "true"}
    subprocess.Popen(
        [TV_APP, f"--remote-debugging-port={CDP_PORT}"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(wait):
        time.sleep(2)
        if is_connected():
            return True
    raise BridgeError("TradingView relancé mais le CDP ne répond toujours pas.")


def set_symbol(symbol: str, settle: float = 1.2) -> None:
    _run(["symbol", "--symbol", symbol])
    time.sleep(settle)


def set_timeframe(tf: str, settle: float = 1.5) -> None:
    _run(["timeframe", "--timeframe", str(tf)])
    time.sleep(settle)


def quote() -> dict:
    return _run(["quote"])


def ohlcv(count: int = 300) -> list[dict]:
    data = _run(["ohlcv", "--count", str(min(count, 500))], timeout=120)
    bars = data.get("bars", [])
    if not bars:
        raise BridgeError("Aucune bougie retournée.")
    return bars


def fetch_timeframe(symbol: str, tf: str, count: int = 300) -> dict:
    """Bascule le graphique et récupère un jeu complet pour un timeframe."""
    set_symbol(symbol)
    set_timeframe(tf)
    return {"symbol": symbol, "timeframe": tf, "bars": ohlcv(count), "quote": quote()}
