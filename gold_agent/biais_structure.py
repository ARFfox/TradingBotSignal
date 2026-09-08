"""AG-02 Structure applique aux membres de la constellation.

Remplace `biais_provisoire()` (deux moyennes mobiles) par une lecture qui
croise DEUX informations independantes par actif :

1. la position des EMA 20/50, normalisee par la distribution historique de
   l'actif lui-meme (auto-calibrage — un seuil devine se trompe d'un
   facteur 2 ou 3 selon l'actif) ;
2. la STRUCTURE de marche : sequence des pivots confirmes (HH+HL haussier,
   LH+LL baissier), via structure.pivots/trend_from_structure — les memes
   briques que l'analyse de l'or, rendues possibles sur GDX, l'argent ou le
   DXY par le cache OHLC (Phase 0 : features symbole-agnostiques).

Regle du SYSTEME.md (13) : un desaccord entre les deux lectures fait
DOUTER — le verdict est neutre, jamais l'avis le plus optimiste.

Module pur : on lui passe le DataFrame OHLC, aucun appel reseau.
"""
from __future__ import annotations

from . import structure as st

MIN_JOURS = 60          # sous ce nombre, on ne conclut rien
FENETRE_PIVOTS = 120    # jours de structure regardes
SEUIL_Z = 0.5           # z de l'ecart EMA au-dela duquel l'EMA vote

VOTE_STRUCTURE = {"haussier": 1.0, "haussier_affaibli": 0.5,
                  "baissier": -1.0, "baissier_affaibli": -0.5,
                  "range": 0.0, "indetermine": 0.0}


def _vote_ema(closes) -> float:
    """+1 / -1 / 0 selon l'ecart EMA20-EMA50 rapporte a SA distribution."""
    import numpy as np
    e20, e50 = closes.ewm(span=20).mean(), closes.ewm(span=50).mean()
    ec = (e20 - e50) / e50
    sigma = float(ec.tail(250).std())
    if not np.isfinite(sigma) or sigma == 0:
        return 0.0
    z = float(ec.iloc[-1]) / sigma
    return 1.0 if z > SEUIL_Z else -1.0 if z < -SEUIL_Z else 0.0


def _vote_structure(highs: list, lows: list) -> tuple[float, str]:
    piv = st.pivots(highs, lows, left=3, right=3)
    t = st.trend_from_structure(piv)
    return VOTE_STRUCTURE.get(t["trend"], 0.0), t["trend"]


def examiner(closes, highs, lows) -> dict | None:
    """Verdict pour UN actif : {biais, ema, structure} ou None si trop court."""
    c = closes.dropna()
    if len(c) < MIN_JOURS:
        return None
    v_ema = _vote_ema(c)

    h = highs.reindex(c.index).ffill().tail(FENETRE_PIVOTS)
    l = lows.reindex(c.index).ffill().tail(FENETRE_PIVOTS)
    if h.isna().any() or l.isna().any() or len(h) < 30:
        v_st, tendance = 0.0, "indetermine"
    else:
        v_st, tendance = _vote_structure(list(h), list(l))

    total = v_ema + v_st
    biais = "haussier" if total >= 1.0 else "baissier" if total <= -1.0 else "neutre"
    return {"biais": biais, "ema": v_ema, "structure": tendance}


def biais_membres(po) -> dict[str, str]:
    """{ticker: haussier|baissier|neutre} depuis le DataFrame OHLC MultiIndex.

    Un actif sans donnees suffisantes est ABSENT du dictionnaire : le Miroir
    le traite alors comme neutre et l'ignore — une absence d'information
    n'est jamais un avis.
    """
    out: dict[str, str] = {}
    try:
        fermetures = po["Close"]
        hauts, bas = po["High"], po["Low"]
    except Exception:
        return out
    for t in fermetures.columns:
        try:
            v = examiner(fermetures[t], hauts.get(t, fermetures[t]),
                         bas.get(t, fermetures[t]))
        except Exception:
            v = None
        if v is not None:
            out[t] = v["biais"]
    return out
