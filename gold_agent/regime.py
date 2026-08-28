"""Détection de régime : volatilité, renversement, épuisement.

L'analyse instantanée lit le marché comme une photo. Or ce qui vient de se
passer change la lecture : une expansion brutale de volatilité invalide des
stops calibrés sur la période calme qui précède, et un renversement violent
après une tendance étirée n'a pas le même sens qu'une simple respiration.

Ce module donne à l'agent la mémoire qui lui manquait.
"""
from __future__ import annotations

from typing import Optional, Sequence

from . import indicators as ind


def regime_volatilite(highs: Sequence[float], lows: Sequence[float],
                      closes: Sequence[float], court: int = 14,
                      long: int = 50) -> dict:
    """Compare la volatilité récente à sa norme.

    Un ATR court très supérieur à l'ATR long signale que le marché vient de
    changer de rythme. Les stops calibrés sur l'ancien régime sont alors trop
    serrés, et les niveaux calculés sur la période calme trop rapprochés.
    """
    atr_c = ind.last_valid(ind.atr(highs, lows, closes, court))
    atr_l = ind.last_valid(ind.atr(highs, lows, closes, long))
    if not atr_c or not atr_l:
        return {"regime": None, "raison": "historique insuffisant"}

    ratio = atr_c / atr_l
    if ratio >= 1.5:
        etat, note = "expansion_forte", ("volatilite en forte expansion — les stops calibres "
                                         "sur la periode precedente sont trop serres")
    elif ratio >= 1.2:
        etat, note = "expansion", "volatilite en hausse"
    elif ratio <= 0.7:
        etat, note = "compression", ("volatilite comprimee — souvent suivie d'une expansion, "
                                     "sans indication de direction")
    else:
        etat, note = "normal", "volatilite dans sa norme"

    return {"regime": etat, "ratio": round(ratio, 2), "atr_court": round(atr_c, 2),
            "atr_long": round(atr_l, 2), "note": note}


def renversement(opens: Sequence[float], highs: Sequence[float],
                 lows: Sequence[float], closes: Sequence[float],
                 fenetre: int = 3, seuil_atr: float = 2.0) -> dict:
    """Le prix a-t-il fait demi-tour violemment sur les dernières bougies ?

    On mesure le rejet : distance entre l'extrême atteint et la clôture,
    rapportée à l'ATR. Un rejet marqué signifie que le mouvement a été
    entierement rendu — ce que la structure en pivots, plus lente, n'a pas
    encore enregistre.
    """
    atr = ind.last_valid(ind.atr(highs, lows, closes, 14))
    if not atr or len(closes) < fenetre + 1:
        return {"renversement": None}

    recents_h = highs[-fenetre:]
    recents_l = lows[-fenetre:]
    plus_haut, plus_bas = max(recents_h), min(recents_l)
    clot = closes[-1]

    rejet_haut = (plus_haut - clot) / atr      # combien du haut a ete rendu
    rejet_bas = (clot - plus_bas) / atr

    if rejet_haut >= seuil_atr and rejet_haut > rejet_bas:
        return {"renversement": "baissier", "ampleur_atr": round(rejet_haut, 2),
                "extreme": round(plus_haut, 2), "cloture": round(clot, 2),
                "note": (f"le prix a atteint {plus_haut:.2f} puis rendu "
                         f"{plus_haut - clot:.2f} points ({rejet_haut:.1f} ATR) — "
                         f"rejet du haut")}
    if rejet_bas >= seuil_atr and rejet_bas > rejet_haut:
        return {"renversement": "haussier", "ampleur_atr": round(rejet_bas, 2),
                "extreme": round(plus_bas, 2), "cloture": round(clot, 2),
                "note": (f"le prix a atteint {plus_bas:.2f} puis repris "
                         f"{clot - plus_bas:.2f} points ({rejet_bas:.1f} ATR) — "
                         f"rejet du bas")}
    return {"renversement": None, "rejet_haut_atr": round(rejet_haut, 2),
            "rejet_bas_atr": round(rejet_bas, 2)}


def score_extension(prix: float, ema_fast: Optional[float],
                    rsi: Optional[float]) -> dict:
    """Extension notée de 0 à 100, sans seuil-falaise.

    Le veto binaire precedent exigeait RSI >= 70 ET ecart >= 5 %. Un RSI a
    69,1 l'eteignait entierement alors que le prix restait etire a +7,3 %.
    Ici chaque composante contribue progressivement : passer de 69 a 70 ne
    change plus rien de brutal.
    """
    if ema_fast is None or rsi is None or not ema_fast:
        return {"score": 0, "niveau": "inconnu", "composantes": {}}

    ecart = (prix - ema_fast) / ema_fast * 100
    ecart_abs = abs(ecart)

    # Ecart a l'EMA : 0 a 60 points, sature a 8 %
    pts_ecart = min(60.0, ecart_abs / 8.0 * 60.0)
    # RSI : 0 a 40 points, commence a compter des 55 (et 45 en survente)
    if rsi >= 55:
        pts_rsi = min(40.0, (rsi - 55) / 25.0 * 40.0)
    elif rsi <= 45:
        pts_rsi = min(40.0, (45 - rsi) / 25.0 * 40.0)
    else:
        pts_rsi = 0.0

    score = pts_ecart + pts_rsi
    if score >= 70:
        niveau = "extreme"
    elif score >= 50:
        niveau = "marquee"
    elif score >= 30:
        niveau = "moderee"
    else:
        niveau = "faible"

    return {"score": round(score, 1), "niveau": niveau,
            "sens": "haussiere" if ecart > 0 else "baissiere",
            "ecart_pct": round(ecart, 2), "rsi": round(rsi, 1),
            "composantes": {"ecart": round(pts_ecart, 1), "rsi": round(pts_rsi, 1)}}
