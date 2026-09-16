"""Adapter CCXT — une API unifiée pour 100+ exchanges (CHANTIER #10).

Ce que CCXT remplace : la pagination, les rate limits et les formats de
symbole écrits à la main dans binance.py — trois choses qui cassent
silencieusement quand on les maintient soi-même (SKILL_OUTILS_EXTERNES §1).

Ce qui NE change PAS : le contrat feeds/ — seau à jetons, backoff, cache
disque dont la taille demandée fait partie du contrat, validation des
bougies. `_fetch` délègue simplement à ccxt. Crypto UNIQUEMENT : le forex,
les matières et les actions restent sur yfinance / Twelve Data.

En panne (ccxt absent, exchange muet), l'appelant retombe sur l'adaptateur
maison feeds/binance.py — le remplacement est réversible par construction.
"""
from __future__ import annotations

from .base import Feed, SeauJetons

INTERVALLES = {"D": "1d", "240": "4h", "60": "1h", "30": "30m",
               "15": "15m", "5": "5m", "1": "1m"}
MAX_PAR_APPEL = 1000


def symbole_ccxt(code_binance: str) -> str:
    """« BTCUSDT » (registre) → « BTC/USDT » (convention ccxt)."""
    s = code_binance.upper().replace("/", "")
    for quote in ("USDT", "USDC", "BUSD", "USD", "EUR", "BTC", "ETH"):
        if s.endswith(quote) and len(s) > len(quote):
            return f"{s[:-len(quote)]}/{quote}"
    return code_binance


class CcxtFeed(Feed):
    """OHLCV via ccxt. L'exchange est INJECTABLE : les tests passent un
    faux objet et aucun test ne touche le réseau (règle 18)."""

    nom = "ccxt_binance"
    exchange_id = "binance"

    def __init__(self, exchange=None, **kw):
        kw.setdefault("seau", SeauJetons(10, 5.0))
        super().__init__(**kw)
        self._ex = exchange

    @property
    def exchange(self):
        if self._ex is None:
            import ccxt
            self._ex = getattr(ccxt, self.exchange_id)(
                {"enableRateLimit": True})
        return self._ex

    def _page(self, sym: str, iv: str, since: int | None, n: int,
              essais: int = 4) -> list:
        """Un appel fetch_ohlcv sous seau + backoff — le seul point réseau."""
        derniere = None
        for k in range(essais):
            self.seau.prendre()
            try:
                return self.exchange.fetch_ohlcv(sym, iv, since=since,
                                                 limit=n)
            except Exception as e:
                derniere = e
                if k < essais - 1:
                    self.sommeil(2 ** k)
        raise RuntimeError(f"{self.nom} : {derniere}")

    def _fetch(self, symbole: str, tf: str, nombre: int) -> list[dict]:
        iv = INTERVALLES.get(tf)
        if iv is None:
            raise ValueError(f"timeframe inconnu : {tf}")
        sym = symbole_ccxt(symbole)
        dur_ms = self.exchange.parse_timeframe(iv) * 1000
        since = self.exchange.milliseconds() - nombre * dur_ms
        out: list = []
        while len(out) < nombre:
            page = self._page(sym, iv, since,
                              min(MAX_PAR_APPEL, nombre - len(out) + 1))
            if not page:
                break
            out.extend(page)
            avance = page[-1][0] + dur_ms
            if avance <= since or len(page) < 2:
                break                        # l'exchange ne progresse plus
            since = avance
        return [{"time": int(t) // 1000, "open": o, "high": h,
                 "low": l, "close": c, "volume": v}
                for t, o, h, l, c, v in out]
