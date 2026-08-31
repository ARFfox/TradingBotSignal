"""Concepts ICT : premium/discount, killzones, phase AMD.

Complète les briques ICT déjà en place (FVG dans structure.py, order blocks
dans patterns.py). AUCUN de ces indicateurs n'est backtesté ici — ils sont
affichés comme CONTEXTE, au même titre que les sessions, et étiquetés comme
tels. Les heuristiques sont volontairement simples et documentées : une
« phase AMD » détectée par un script n'est qu'une description du range
récent, pas une lecture dans les intentions des institutionnels.
"""
from __future__ import annotations

import datetime as dt
from typing import Sequence

# Killzones ICT classiques, en UTC : les fenetres ou la liquidite se
# concentre. Londres ouvre, New York ouvre.
KILLZONES = {"Londres": (7, 10), "New York": (12, 15)}


def killzone_active(ts: int) -> str | None:
    h = dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour
    for nom, (h0, h1) in KILLZONES.items():
        if h0 <= h < h1:
            return nom
    return None


def premium_discount(highs: Sequence[float], lows: Sequence[float],
                     prix: float, fenetre: int = 60) -> dict:
    """Position du prix dans le range récent.

    ICT : sous l'équilibre (50 %) = discount (zone d'achat preferee),
    au-dessus = premium (zone de vente preferee). C'est une regle de bon
    sens — acheter bas dans le range — pas une magie.
    """
    h = max(highs[-fenetre:])
    l = min(lows[-fenetre:])
    if h <= l:
        return {"zone": None}
    pct = (prix - l) / (h - l) * 100
    if pct <= 38:
        zone = "discount"
    elif pct >= 62:
        zone = "premium"
    else:
        zone = "équilibre"
    return {"zone": zone, "position_pct": round(pct, 1),
            "haut_range": round(h, 2), "bas_range": round(l, 2),
            "equilibre": round((h + l) / 2, 2)}


def phase_amd(opens: Sequence[float], highs: Sequence[float],
              lows: Sequence[float], closes: Sequence[float],
              atr: float, fenetre: int = 48) -> dict:
    """Heuristique Accumulation / Manipulation / Distribution (Power of 3).

    - Accumulation : range etroit (< 2,5 ATR sur la fenetre recente)
    - Manipulation : une meche recente BALAIE l'extreme du range puis
      recloture dedans (prise de liquidite)
    - Distribution : expansion directionnelle (> 4 ATR de deplacement net)
    """
    if len(closes) < fenetre + 12 or not atr:
        return {"phase": None}

    base_h = max(highs[-fenetre - 12:-12])
    base_l = min(lows[-fenetre - 12:-12])
    largeur = (base_h - base_l) / atr

    recents_h = highs[-12:]
    recents_l = lows[-12:]
    recents_c = closes[-12:]

    balayage_haut = max(recents_h) > base_h and recents_c[-1] < base_h
    balayage_bas = min(recents_l) < base_l and recents_c[-1] > base_l
    deplacement = abs(closes[-1] - closes[-fenetre]) / atr

    if balayage_haut or balayage_bas:
        sens = "du haut (liquidité au-dessus prise)" if balayage_haut \
            else "du bas (liquidité en dessous prise)"
        return {"phase": "manipulation", "detail": f"balayage {sens}, retour dans le range",
                "range": [round(base_l, 2), round(base_h, 2)]}
    if deplacement >= 4:
        return {"phase": "distribution",
                "detail": f"expansion de {deplacement:.1f} ATR "
                          f"({'hausse' if closes[-1] > closes[-fenetre] else 'baisse'})"}
    if largeur <= 2.5:
        return {"phase": "accumulation",
                "detail": f"range de {largeur:.1f} ATR — compression",
                "range": [round(base_l, 2), round(base_h, 2)]}
    return {"phase": "indéterminée", "detail": f"range {largeur:.1f} ATR, deplacement {deplacement:.1f} ATR"}


def analyse_ict(bars: list[dict], atr: float) -> dict:
    o = [b["open"] for b in bars]
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    return {
        "premium_discount": premium_discount(h, l, c[-1]),
        "killzone": killzone_active(bars[-1]["time"]),
        "amd": phase_amd(o, h, l, c, atr),
        "note": "contexte ICT — heuristiques non backtestees",
    }
