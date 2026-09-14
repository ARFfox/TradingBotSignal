"""CRT et IFVG — deux familles de setups du skill strategies-entree.

Ce sont des SCANNERS historiques : ils parcourent les bougies et emettent
des signaux au format strategy.Signal, sans jamais regarder devant (le
signal a l'index i n'utilise que bars[:i+1]). C'est ce qui les rend
backtestables par le walk-forward — et c'est la SEULE chose qui decidera
s'ils servent : ces methodes viennent d'Instagram, populaires n'est pas
profitables. AUCUNE n'emet en live sans verdict AUTORISE.
"""
from __future__ import annotations

import datetime as dt

from . import indicators as ind, strategy as sg, structure as st

MARGE_ATR = 0.2          # marge du stop au-dela de l'extreme
CORPS_DEPLACEMENT = 1.3  # corps >= 1,3 x le corps moyen des 20 dernieres
RR_MIN = 1.5
EXPIRATION_IFVG = 10     # bougies apres l'inversion
GAP_MAX_VIE = 120        # un FVG trop vieux n'interesse plus personne


def _heure(ts: int) -> int:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour


def _jour(ts: int):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()


# --------------------------------------------------------------------------
# CRT — Candle Range Theory
# --------------------------------------------------------------------------
def crt(bars: list[dict], p: sg.Params, heure_ref: int = 13) -> list[sg.Signal]:
    """Bougie de reference (9h New York ~ 13h UTC) -> balayage REJETE
    (depasse le bord mais CLOTURE dedans — c'est le coeur du pattern :
    sans cette condition on detecte aussi les vraies cassures, et on perd
    sur toutes) -> deplacement oppose a corps franc -> entree au retour.
    """
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    o = [b["open"] for b in bars]
    atr = ind.atr(h, l, c, 14)
    out: list[sg.Signal] = []

    i = 0
    n = len(bars)
    while i < n:
        if _heure(bars[i]["time"]) != heure_ref:
            i += 1
            continue
        jour = _jour(bars[i]["time"])
        hr, lr = h[i], l[i]                      # le range de reference
        # chercher le balayage dans les bougies suivantes du MEME jour
        k = i + 1
        while k < n - 2 and _jour(bars[k]["time"]) == jour:
            balaye_haut = h[k] > hr and c[k] <= hr      # piege, pas cassure
            balaye_bas = l[k] < lr and c[k] >= lr
            if not (balaye_haut or balaye_bas):
                k += 1
                continue
            # deplacement : la bougie suivante cloture a l'oppose du
            # balayage, avec un corps >= 1,3 x le corps moyen (20)
            j = k + 1
            corps = abs(c[j] - o[j])
            corps_moyen = (sum(abs(c[x] - o[x])
                               for x in range(max(0, j - 20), j)) / 20) or 1e-9
            a = atr[j] or 0
            deplacement_ok = corps >= CORPS_DEPLACEMENT * corps_moyen
            if balaye_haut and c[j] < o[j] and deplacement_ok:
                sens, stop, objectif = "vente", h[k] + MARGE_ATR * a, lr
            elif balaye_bas and c[j] > o[j] and deplacement_ok:
                sens, stop, objectif = "achat", l[k] - MARGE_ATR * a, hr
            else:
                k += 1
                continue
            # Entree au retracement de 50 % de la bougie de balayage —
            # l'enseignement standard du corpus. Entrer au prix de cloture
            # du deplacement donnerait un R:R structurellement mauvais
            # (le mouvement est deja parti). On attend le retour, 3 bougies
            # maximum : au-dela, le contexte qui a cree le piege est mort.
            entree = (h[k] + l[k]) / 2
            for f in range(j + 1, min(j + 4, n)):
                touche = (h[f] >= entree if sens == "vente" else l[f] <= entree)
                if not touche:
                    continue
                risque = abs(entree - stop)
                gain = abs(objectif - entree)
                if risque > 0 and gain / risque >= RR_MIN:
                    out.append(sg.Signal(index=f, sens=sens, entree=entree,
                                         stop=stop, objectif=objectif,
                                         rr=round(gain / risque, 2),
                                         motif=f"CRT {heure_ref}h : balayage "
                                               f"{'haut' if balaye_haut else 'bas'}"
                                               f" rejeté, retour à 50 %"))
                break
            break                                # un CRT par bougie de reference
        i = k + 1 if k > i else i + 1
    return out


# --------------------------------------------------------------------------
# IFVG — Inversion Fair Value Gap
# --------------------------------------------------------------------------
def ifvg(bars: list[dict], p: sg.Params) -> list[sg.Signal]:
    """Un FVG qui change de role. Seule la CLOTURE de l'autre cote compte
    (une meche qui traverse ne compte pas) ; entree au retest du gap dans
    son nouveau role, stop de l'autre cote + 0,2 ATR, TP au prochain pivot
    confirme dans le sens du trade. Expire 10 bougies apres l'inversion.
    """
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    atr = ind.atr(h, l, c, 14)
    out: list[sg.Signal] = []
    gaps: list[dict] = []       # {type, bas, haut, ne, inverse_a|None}

    for i in range(2, len(bars)):
        # nouveaux FVG (regle des trois bougies)
        if l[i] > h[i - 2]:
            gaps.append({"type": "haussier", "bas": h[i - 2], "haut": l[i],
                         "ne": i, "inverse_a": None})
        elif h[i] < l[i - 2]:
            gaps.append({"type": "baissier", "bas": h[i], "haut": l[i - 2],
                         "ne": i, "inverse_a": None})

        gaps = [g for g in gaps if i - g["ne"] <= GAP_MAX_VIE]
        a = atr[i] or 0
        for g in gaps:
            if g["inverse_a"] is None:
                # inversion : une CLOTURE de l'autre cote du gap
                if g["type"] == "haussier" and c[i] < g["bas"]:
                    g["inverse_a"] = i          # support devenu resistance
                elif g["type"] == "baissier" and c[i] > g["haut"]:
                    g["inverse_a"] = i          # resistance devenue support
                continue
            if i - g["inverse_a"] > EXPIRATION_IFVG:
                continue
            if i == g["inverse_a"]:
                continue
            # retest du gap dans son nouveau role
            if g["type"] == "haussier" and h[i] >= g["bas"] and a:
                entree, stop = g["bas"], g["haut"] + MARGE_ATR * a
                piv = st.pivots(h[: i + 1], l[: i + 1], 3, 3)["lows"]
                cibles = [x["price"] for x in piv if x["price"] < entree]
                if not cibles:
                    continue
                objectif, sens = max(cibles), "vente"
            elif g["type"] == "baissier" and l[i] <= g["haut"] and a:
                entree, stop = g["haut"], g["bas"] - MARGE_ATR * a
                piv = st.pivots(h[: i + 1], l[: i + 1], 3, 3)["highs"]
                cibles = [x["price"] for x in piv if x["price"] > entree]
                if not cibles:
                    continue
                objectif, sens = min(cibles), "achat"
            else:
                continue
            risque = abs(entree - stop)
            gain = abs(objectif - entree)
            if risque > 0 and gain / risque >= RR_MIN:
                out.append(sg.Signal(index=i, sens=sens, entree=entree,
                                     stop=stop, objectif=objectif,
                                     rr=round(gain / risque, 2),
                                     motif=f"IFVG {g['type']} inversé"))
                g["inverse_a"] = -10 ** 9        # un seul signal par gap
    return out
