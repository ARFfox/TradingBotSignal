"""ORB et retest du POC — la famille volume/sessions du skill.

Memes principes que strategies_entree : scanners historiques sans
lookahead, format strategy.Signal, backtestables — et RIEN n'emet sans
verdict AUTORISE du walk-forward.

⚠️ Sur l'or spot le volume est absent (Twelve Data) : le profil et le
VWAP degenerent en poids temporels et le disent. Le backtest jugera si
ces degradations gardent un edge — pas nous.
"""
from __future__ import annotations

import datetime as dt

from . import indicators as ind, profil_volume as pv, sessions, strategy as sg

RR_MIN = 1.5
ORB_HEURE_UTC = 13          # ouverture de la session de New York (skill §6)
ORB_FENETRE_H = 1           # entree uniquement dans la premiere heure
POC_FENETRE = 200           # bougies du profil glissant
POC_RECALCUL = 20           # recalcul du profil toutes les N bougies
POC_ECART_ATR = 1.5         # eloignement minimal avant le retest


def _dt(ts: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc)


# --------------------------------------------------------------------------
# ORB — Opening Range Breakout (New York)
# --------------------------------------------------------------------------
def orb(bars: list[dict], p: sg.Params, marche: str = "matieres",
        minutes_range: int = 15) -> list[sg.Signal]:
    """Range des 15 premieres minutes de New York -> cassure EN CLOTURE ->
    confirmation VWAP de session -> entree AU RETEST du bord casse (pas a
    la cassure : entrer sur la cassure, c'est acheter le haut du mouvement)
    -> fenetre stricte : premiere heure de la session seulement.
    """
    sessions._refuser_crypto(marche)     # le crypto n'a pas de session
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    out: list[sg.Signal] = []

    # decoupage par jour
    jours: dict = {}
    for i, b in enumerate(bars):
        jours.setdefault(_dt(b["time"]).date(), []).append(i)

    for jour, idx in jours.items():
        ouverture = [i for i in idx
                     if _dt(bars[i]["time"]).hour == ORB_HEURE_UTC
                     and _dt(bars[i]["time"]).minute < minutes_range]
        if not ouverture:
            continue
        i_ancre = ouverture[0]
        hr = max(h[i] for i in ouverture)
        lr = min(l[i] for i in ouverture)
        hauteur = hr - lr
        if hauteur <= 0:
            continue
        fin_fenetre = ORB_HEURE_UTC + ORB_FENETRE_H
        casse = None      # ("achat"|"vente", index de cassure)
        for i in idx:
            if i <= ouverture[-1]:
                continue
            d_ = _dt(bars[i]["time"])
            if d_.hour >= fin_fenetre:
                break                     # hors fenetre : le range est mort
            if casse is None:
                if c[i] > hr:
                    casse = ("achat", i)
                elif c[i] < lr:
                    casse = ("vente", i)
                continue
            sens, i_casse = casse
            bord = hr if sens == "achat" else lr
            retest = (l[i] <= bord if sens == "achat" else h[i] >= bord)
            if not retest:
                continue
            # confirmation : le prix du bon cote du VWAP de session
            v, _src = sessions.vwap(bars[: i + 1], depuis_index=i_ancre)
            if v is None or (sens == "achat" and c[i] < v) \
                    or (sens == "vente" and c[i] > v):
                break                     # confirmation absente : on passe
            entree = bord
            stop = lr if sens == "achat" else hr
            objectif = bord + hauteur if sens == "achat" else bord - hauteur
            risque = abs(entree - stop)
            if risque > 0 and abs(objectif - entree) / risque >= RR_MIN - 0.5:
                # le RR structurel de l'ORB est 1:1 par construction (TP1 =
                # 1 x la hauteur, SL = l'autre bord) : exiger 1,5 le tuerait
                # d'office — c'est au backtest de dire s'il paie quand meme.
                out.append(sg.Signal(index=i, sens=sens, entree=entree,
                                     stop=stop, objectif=objectif,
                                     rr=round(abs(objectif - entree) / risque, 2),
                                     motif=f"ORB NY {minutes_range} min, retest"))
            break                         # un ORB par jour
    return out


# --------------------------------------------------------------------------
# Retest du POC (Volume Profile)
# --------------------------------------------------------------------------
def poc_retest(bars: list[dict], p: sg.Params) -> list[sg.Signal]:
    """Le prix s'eloigne du POC de plus de 1,5 ATR, revient le tester, une
    bougie cloture dans le sens du retour -> entree au rejet, SL derriere
    le POC + 0,3 ATR, TP au bord de la zone de valeur — JAMAIS dans un LVN
    (le prix y passe sans s'arreter : l'ordre ne se remplit pas).
    """
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    o = [b["open"] for b in bars]
    atr = ind.atr(h, l, c, 14)
    out: list[sg.Signal] = []
    profil, profil_a = None, -10 ** 9

    for i in range(POC_FENETRE + 5, len(bars)):
        if i - profil_a >= POC_RECALCUL:
            profil = pv.profil_volume(bars[i - POC_FENETRE:i])
            profil_a = i
        a = atr[i] or 0
        if not profil or not a:
            continue
        poc = profil["poc"]
        # le POC est teste sur CETTE bougie...
        if not (l[i] <= poc <= h[i]):
            continue
        # ...apres un eloignement franc dans les 30 dernieres bougies
        ecarts = [c[j] - poc for j in range(max(0, i - 30), i)]
        venu_du_haut = max(ecarts, default=0) > POC_ECART_ATR * a
        venu_du_bas = min(ecarts, default=0) < -POC_ECART_ATR * a
        if venu_du_haut and c[i] > poc and c[i] > o[i]:
            sens, entree = "achat", c[i]
            stop = poc - 0.3 * a
            objectif = profil["vah"]
        elif venu_du_bas and c[i] < poc and c[i] < o[i]:
            sens, entree = "vente", c[i]
            stop = poc + 0.3 * a
            objectif = profil["val"]
        else:
            continue
        # jamais de TP dans un LVN : glisser vers le HVN le plus proche
        # dans le sens du trade, ou passer son tour
        if pv.dans_lvn(objectif, profil):
            hvn = [x for x in profil["hvn"]
                   if (x > entree if sens == "achat" else x < entree)]
            if not hvn:
                continue
            objectif = min(hvn) if sens == "achat" else max(hvn)
        risque = abs(entree - stop)
        gain = abs(objectif - entree)
        if risque > 0 and gain / risque >= RR_MIN:
            out.append(sg.Signal(index=i, sens=sens, entree=entree,
                                 stop=stop, objectif=objectif,
                                 rr=round(gain / risque, 2),
                                 motif=f"retest POC ({profil['source_poids']})"))
    return out
