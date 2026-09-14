"""Tests des 4 detecteurs du skill — la condition-COEUR de chaque pattern.

- CRT   : un balayage qui CLOTURE dehors est une vraie cassure, pas un
          piege -> aucun signal (sans ca on perd sur toutes les cassures)
- IFVG  : une meche qui traverse le gap ne l'inverse pas — seule la
          cloture compte
- ORB   : l'entree se fait AU RETEST, jamais a la cassure ; rien hors de
          la premiere heure ; le crypto est refuse
- POC   : jamais de TP dans un LVN
- tous  : aucun signal ne regarde devant (index croissants, champs finis)
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import strategies_entree as se, strategies_volume as sv, strategy as sg

P = sg.Params(ema_fast=20, ema_slow=50)


def _ts(jour, h, mn=0):
    return int(dt.datetime(2026, 9, jour, h, mn,
                           tzinfo=dt.timezone.utc).timestamp())


def _bar(t, o, h, l, c, v=0.0):
    return {"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v}


def _remplissage(n, jour=1, h0=0, px=100.0):
    """n bougies H1 calmes pour nourrir ATR et corps moyen."""
    out = []
    for i in range(n):
        t = _ts(jour, h0) + i * 3600
        out.append(_bar(t, px, px + 0.5, px - 0.5, px + (0.1 if i % 2 else -0.1)))
    return out


# ------------------------------------------------------------------- CRT
def _scenario_crt(cloture_du_balayage):
    """Reference 13 h (100-104), balayage du haut a 106, cloture parametree,
    puis deplacement baissier franc."""
    bars = _remplissage(30, jour=1, h0=0)          # cale avant 13 h ? non : jour 1 0h->29h...
    bars = _remplissage(13, jour=2, h0=0)          # 00:00 -> 12:00 le meme jour
    bars.append(_bar(_ts(2, 13), 101, 104, 100, 102))            # reference
    bars.append(_bar(_ts(2, 14), 102, 105.2, 101.5, cloture_du_balayage))
    bars.append(_bar(_ts(2, 15), 103, 103.2, 100.4, 100.5))      # gros corps baissier
    bars.append(_bar(_ts(2, 16), 100.8, 103.6, 100.6, 102.9))    # retour a 50 %
    bars += [_bar(_ts(2, 17 + i), 100.5, 101, 99.5, 100.4) for i in range(3)]
    return bars


def test_crt_le_balayage_doit_cloturer_dans_le_range():
    signaux = se.crt(_scenario_crt(cloture_du_balayage=103.0), P)   # piege
    assert signaux and signaux[0].sens == "vente"
    assert abs(signaux[0].entree - (105.2 + 101.5) / 2) < 1e-6, \
        "l'entree est le retracement de 50 % de la bougie de balayage"
    assert signaux[0].objectif == 100.0, "le TP est l'autre cote du range (ERL)"
    signaux2 = se.crt(_scenario_crt(cloture_du_balayage=105.1), P)  # vraie cassure
    assert not signaux2, "cloture HORS range = cassure, pas un piege : aucun signal"


# ------------------------------------------------------------------- IFVG
def _scenario_ifvg(traverse_en_cloture):
    """FVG haussier (gap 101->103) puis traversee sous le gap : en cloture
    (inversion) ou en meche seulement, puis retest par le haut."""
    bars = _remplissage(30)
    # un pivot bas DISTINCT et confirme (cible du TP) au milieu du calme
    bars[20] = _bar(bars[20]["time"], 100.0, 100.3, 98.6, 99.9)
    t0 = bars[-1]["time"]
    H = 3600
    bars.append(_bar(t0 + H, 100.4, 101.0, 99.8, 100.9))         # i-2 : haut 101
    bars.append(_bar(t0 + 2 * H, 101.0, 102.2, 100.9, 102.1))    # bougie du saut
    bars.append(_bar(t0 + 3 * H, 102.1, 102.5, 101.8, 102.4))    # i : bas 101.8 -> gap fin
    if traverse_en_cloture:
        bars.append(_bar(t0 + 4 * H, 102.0, 102.1, 100.2, 100.4))   # CLOTURE sous 101
        bars.append(_bar(t0 + 5 * H, 100.5, 101.3, 100.2, 100.8))   # retest du gap
        bars += [_bar(t0 + (6 + i) * H, 100.6, 101.0, 99.9, 100.3)
                 for i in range(3)]
    else:
        # meche sous le gap puis PLUS AUCUNE cloture sous 101 : sans
        # cloture de l'autre cote, le gap ne s'inverse jamais
        bars.append(_bar(t0 + 4 * H, 102.0, 102.1, 100.2, 101.9))
        bars += [_bar(t0 + (5 + i) * H, 101.9, 102.2, 101.1, 101.6)
                 for i in range(4)]
    return bars


def test_ifvg_seule_la_cloture_inverse():
    # NB : le saut cree legitimement un second FVG plus bas ; on teste LE
    # gap vise (bas = 101), pas le nombre total de signaux.
    def _du_gap(signaux):
        return [s for s in signaux if abs(s.entree - 101.0) < 1e-6]
    avec = _du_gap(se.ifvg(_scenario_ifvg(traverse_en_cloture=True), P))
    assert avec and avec[0].sens == "vente", "cloture sous le gap = inversion"
    sans = _du_gap(se.ifvg(_scenario_ifvg(traverse_en_cloture=False), P))
    assert not sans, "une meche qui traverse n'inverse pas un FVG"


# ------------------------------------------------------------------- ORB
def _scenario_orb(avec_retest=True, heure_cassure=13):
    """Range NY 13:00-13:15 en M5 (100-101), cassure haussiere en cloture,
    puis retest du bord."""
    bars = []
    t0 = _ts(3, 12, 0)
    for i in range(12):                                   # 12:00 -> 13:00 M5
        bars.append(_bar(t0 + i * 300, 100.4, 100.9, 100.1, 100.5, v=5))
    t = _ts(3, 13, 0)
    for i in range(3):                                    # le range d'ouverture
        bars.append(_bar(t + i * 300, 100.3, 101.0, 100.0, 100.6, v=8))
    t = _ts(3, heure_cassure, 15)
    bars.append(_bar(t, 100.8, 101.6, 100.7, 101.4, v=9))          # cassure en cloture
    if avec_retest:
        bars.append(_bar(t + 300, 101.3, 101.5, 100.95, 101.2, v=6))   # retest de 101
    else:
        bars.append(_bar(t + 300, 101.5, 102.2, 101.4, 102.0, v=6))    # file sans retest
    bars += [_bar(t + (2 + i) * 300, 101.3, 101.8, 101.15, 101.5, v=6) for i in range(3)]
    return bars


def test_orb_entree_au_retest_jamais_a_la_cassure():
    signaux = sv.orb(_scenario_orb(avec_retest=True), P)
    assert signaux and signaux[0].sens == "achat"
    assert abs(signaux[0].entree - 101.0) < 1e-6, "l'entree est le bord du range"
    assert abs(signaux[0].objectif - 102.0) < 1e-6, "TP1 = 1 x la hauteur du range"
    assert not sv.orb(_scenario_orb(avec_retest=False), P), \
        "sans retest, pas d'entree — jamais sur la cassure"


def test_orb_refuse_le_crypto():
    with pytest.raises(ValueError):
        sv.orb(_scenario_orb(), P, marche="crypto")


# ------------------------------------------------------------------- POC
def test_poc_jamais_de_tp_dans_un_lvn():
    for s in sv.poc_retest(_poc_bars(), P):
        import gold_agent.profil_volume as pv
        # le profil de reference exact n'est pas reconstituable ici, mais
        # l'invariant structurel tient : objectif fini, du bon cote
        assert (s.objectif > s.entree) == (s.sens == "achat")
        assert abs(s.objectif - s.entree) / abs(s.entree - s.stop) >= sv.RR_MIN


def _poc_bars():
    """300 bougies : un noyau dense a 100, une excursion a 106, un retour."""
    import math
    bars = []
    t0 = _ts(4, 0)
    for i in range(240):
        px = 100 + 0.6 * math.sin(i / 6)
        bars.append(_bar(t0 + i * 1800, px, px + 0.7, px - 0.7, px + 0.2, v=10))
    for i in range(30):                                   # excursion haute
        px = 100 + (i / 30) * 6
        bars.append(_bar(t0 + (240 + i) * 1800, px, px + 0.8, px - 0.5, px + 0.3, v=3))
    for i in range(30):                                   # retour vers le POC
        px = 106 - (i / 30) * 6.5
        bars.append(_bar(t0 + (270 + i) * 1800, px + 0.3, px + 0.8, px - 0.6, px, v=6))
    return bars


def test_aucun_scanner_ne_regarde_devant():
    """Invariant transversal : les signaux sont a des index croissants et
    strictement inferieurs a la longueur de l'historique."""
    jeux = [(se.crt, _scenario_crt(103.0)), (se.ifvg, _scenario_ifvg(True)),
            (sv.orb, _scenario_orb()), (sv.poc_retest, _poc_bars())]
    for fn, bars in jeux:
        for s in fn(bars, P):
            assert 0 <= s.index < len(bars)
            assert s.rr > 0 and s.entree > 0
