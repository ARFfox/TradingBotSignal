"""Adapter Bybit v5 — la redondance crypto : meme contrat que Binance,
pour que le systeme survive a une panne d'une des deux sources.
"""
from __future__ import annotations

from .base import Feed, SeauJetons

URL = "https://api.bybit.com/v5/market/kline"
INTERVALLES = {"D": "D", "240": "240", "60": "60", "30": "30",
               "15": "15", "5": "5", "1": "1"}
MAX_PAR_APPEL = 1000


class Bybit(Feed):
    nom = "bybit"

    def __init__(self, **kw):
        kw.setdefault("seau", SeauJetons(10, 5.0))
        super().__init__(**kw)

    def _fetch(self, symbole: str, tf: str, nombre: int) -> list[dict]:
        iv = INTERVALLES.get(tf)
        if iv is None:
            raise ValueError(f"timeframe inconnu : {tf}")
        out: list[dict] = []
        fin_ms = None
        while len(out) < nombre:
            n = min(MAX_PAR_APPEL, nombre - len(out))
            url = (f"{URL}?category=spot&symbol={symbole}"
                   f"&interval={iv}&limit={n}")
            if fin_ms is not None:
                url += f"&end={fin_ms}"
            rep = self._requete(url)
            lignes = ((rep.get("result") or {}).get("list")) or []
            if not lignes:
                break
            # Bybit renvoie du plus RECENT au plus ancien.
            page = [{"time": int(l[0]) // 1000, "open": l[1], "high": l[2],
                     "low": l[3], "close": l[4], "volume": l[5]}
                    for l in reversed(lignes)]
            out = page + out
            fin_ms = int(lignes[-1][0]) - 1
            if len(lignes) < n:
                break
        return out
