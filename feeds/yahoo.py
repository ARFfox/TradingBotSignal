"""Adapter Yahoo (yfinance) — forex, matieres premieres, actions.

yfinance limite l'intraday : 1 h sur ~730 jours, 30/15/5 min sur 60 jours.
C'est la profondeur qu'on annonce, pas une promesse de plus.
"""
from __future__ import annotations

from .base import Feed, SeauJetons

# Pas de "240" : yfinance n'a pas de 4 h natif, et servir du 1 h sous une
# etiquette H4 serait un mensonge de donnees. Qui veut du H4 l'agrege.
INTERVALLES = {"D": ("1d", "3y"), "60": ("1h", "730d"),
               "30": ("30m", "60d"), "15": ("15m", "60d"), "5": ("5m", "60d")}


class Yahoo(Feed):
    nom = "yahoo"

    def __init__(self, **kw):
        kw.setdefault("seau", SeauJetons(5, 1.0))
        super().__init__(**kw)

    def _telecharger(self, symbole: str, intervalle: str, periode: str):
        """Le point reseau de cet adapter — remplace par les tests."""
        import warnings
        warnings.filterwarnings("ignore")
        import yfinance as yf
        return yf.download(symbole, period=periode, interval=intervalle,
                           progress=False, auto_adjust=True)

    def _fetch(self, symbole: str, tf: str, nombre: int) -> list[dict]:
        if tf not in INTERVALLES:
            raise ValueError(f"timeframe inconnu : {tf}")
        intervalle, periode = INTERVALLES[tf]
        self.seau.prendre()
        df = self._telecharger(symbole, intervalle, periode)
        if df is None or df.empty:
            return []
        # yfinance : colonnes MultiIndex meme pour un seul ticker
        if hasattr(df.columns, "levels"):
            df = df.xs(symbole, axis=1, level=-1)
        out = []
        for ts, row in df.iterrows():
            out.append({"time": int(ts.timestamp()), "open": row.get("Open"),
                        "high": row.get("High"), "low": row.get("Low"),
                        "close": row.get("Close"),
                        "volume": row.get("Volume", 0.0)})
        return out
