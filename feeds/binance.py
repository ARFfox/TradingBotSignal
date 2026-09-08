"""Adapter Binance spot — OHLCV sans cle API.

/api/v3/klines : 1000 bougies max par appel -> pagination par endTime pour
les gros historiques. Limite officielle 1200 poids/min ; le seau est regle
bien en dessous (5 req/s) parce qu'on n'est pas presses et que se faire
bannir l'IP couterait plus cher que d'attendre.
"""
from __future__ import annotations

from .base import Feed, SeauJetons

URL = "https://api.binance.com/api/v3/klines"
INTERVALLES = {"D": "1d", "240": "4h", "60": "1h", "30": "30m",
               "15": "15m", "5": "5m", "1": "1m"}
MAX_PAR_APPEL = 1000


class Binance(Feed):
    nom = "binance"

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
            url = f"{URL}?symbol={symbole}&interval={iv}&limit={n}"
            if fin_ms is not None:
                url += f"&endTime={fin_ms}"
            lignes = self._requete(url)
            if not lignes:
                break
            page = [{"time": int(l[0]) // 1000, "open": l[1], "high": l[2],
                     "low": l[3], "close": l[4], "volume": l[5]}
                    for l in lignes]
            out = page + out
            fin_ms = int(lignes[0][0]) - 1     # page precedente
            if len(lignes) < n:
                break                          # debut de l'historique atteint
        return out
