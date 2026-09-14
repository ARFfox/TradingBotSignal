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


# --------------------------------------------------------------------------
# Donnees de POSITIONNEMENT (futures, publiques, sans cle) — le trio que le
# COT hebdomadaire ne donne pas : funding, open interest, ratio long/short
# des gros comptes, QUOTIDIENS. C'est l'equivalent crypto du COT.
# --------------------------------------------------------------------------
URL_FUTURES = "https://fapi.binance.com"


class BinanceFutures(Feed):
    nom = "binance_futures"

    def __init__(self, **kw):
        kw.setdefault("seau", SeauJetons(10, 4.0))
        super().__init__(**kw)

    def funding(self, symbole: str) -> dict | None:
        """Dernier taux de financement (8 h). Positif = les longs payent
        les shorts : le positionnement long est charge."""
        rep = self._requete(f"{URL_FUTURES}/fapi/v1/premiumIndex?symbol={symbole}")
        if not isinstance(rep, dict) or "lastFundingRate" not in rep:
            return None
        return {"taux_pct": round(float(rep["lastFundingRate"]) * 100, 4),
                "prochain_ts": int(rep.get("nextFundingTime", 0)) // 1000}

    def open_interest(self, symbole: str, heures: int = 24) -> dict | None:
        """Variation de l'open interest : l'argent qui entre ou qui sort."""
        n = max(2, min(48, heures + 1))
        rep = self._requete(f"{URL_FUTURES}/futures/data/openInterestHist"
                            f"?symbol={symbole}&period=1h&limit={n}")
        if not isinstance(rep, list) or len(rep) < 2:
            return None
        debut = float(rep[0]["sumOpenInterest"])
        fin = float(rep[-1]["sumOpenInterest"])
        if debut <= 0:
            return None
        return {"actuel": round(fin, 1),
                "variation_pct": round((fin / debut - 1) * 100, 2),
                "heures": len(rep) - 1}

    def ratio_long_short(self, symbole: str) -> dict | None:
        """Ratio long/short des POSITIONS des gros comptes (top traders)."""
        rep = self._requete(f"{URL_FUTURES}/futures/data/topLongShortPositionRatio"
                            f"?symbol={symbole}&period=1h&limit=1")
        if not isinstance(rep, list) or not rep:
            return None
        x = rep[-1]
        return {"ratio": round(float(x["longShortRatio"]), 3),
                "part_long_pct": round(float(x["longAccount"]) * 100, 1)}
