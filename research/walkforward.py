"""Protocole walk-forward — LE module qui decide qui a le droit d'emettre.

Regle 2 du SYSTEME.md : aucune strategie n'emet sans avoir passe ce
protocole. Il repond a UNE question : la regle mecanique gagne-t-elle sur
des fenetres de test qu'elle n'a jamais vues, coûts compris, dans au moins
deux regimes de marche ?

Methode :
- fenetres glissantes : un segment d'echauffement (les indicateurs EMA200,
  pivots... ont besoin d'historique) puis un segment de TEST ; on avance
  d'un pas et on recommence ;
- PURGE entre echauffement et test : les signaux nes dans la zone de purge
  sont jetes — aucune fuite d'information entre segments ;
- les parametres sont FIXES a l'avance (ceux mesures du projet) : rien
  n'est optimise dans la boucle, donc rien ne peut sur-apprendre ;
- chaque trade est etiquete par son regime a l'entree (tendance / range,
  deduit de l'ecart EMA rapporte a l'ATR — jamais choisi a la main) ;
- verdict AUTORISE seulement si : >= 30 trades, >= 2 regimes couverts,
  profit factor > 1,3, R moyen > 0, et au moins la moitie des fenetres
  EVALUABLES positives (une fenetre vote a partir de 3 trades resolus).
  Un seul critere qui manque -> REFUSE, avec le motif.

Module pur : on lui passe les bougies, il ne touche jamais au reseau.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gold_agent import indicators as ind, strategy as sg  # noqa: E402

PURGE = 5                    # bougies jetees entre echauffement et test
# Une fenetre ne VOTE (positive/negative) que si elle contient assez de
# trades : une fenetre d'un seul trade est negative ~50 % du temps meme
# pour une regle gagnante — la compter biaiserait le verdict contre les
# strategies parcimonieuses, qui sont precisement celles qu'on veut.
# Les trades des petites fenetres comptent quand meme dans l'agregat.
TRADES_MIN_FENETRE = 3
TRADES_MIN = 30
REGIMES_MIN = 2
PF_MIN = 1.3
PART_FENETRES_POSITIVES = 0.5


@dataclass
class Resultat:
    instrument: str
    tf: str
    fenetres: int = 0
    fenetres_positives: int = 0
    fenetres_evaluables: int = 0
    trades: int = 0
    r_total: float = 0.0
    r_moyen: float = 0.0
    taux_reussite: float = 0.0
    profit_factor: float = 0.0
    pire_creux: float = 0.0
    regimes: dict = field(default_factory=dict)   # {regime: nb trades}
    autorise: bool = False
    motif: str = ""


def _regime_a(bars: list[dict], i: int) -> str:
    """Regime a l'entree du trade : tendance si l'ecart EMA20-50 depasse
    l'ATR, range sinon. Deduit des donnees, jamais choisi."""
    closes = [b["close"] for b in bars[: i + 1]]
    highs = [b["high"] for b in bars[: i + 1]]
    lows = [b["low"] for b in bars[: i + 1]]
    if len(closes) < 60:
        return "indetermine"
    e20 = ind.ema(closes, 20)[-1]
    e50 = ind.ema(closes, 50)[-1]
    a = ind.atr(highs, lows, closes, 14)[-1]
    if not (e20 and e50 and a):
        return "indetermine"
    return "tendance" if abs(e20 - e50) > a else "range"


def fenetres(n: int, echauffement: int, test: int, pas: int) -> list[tuple]:
    """[(debut_segment, debut_test, fin_test), ...] — la derniere fenetre
    peut etre plus courte mais jamais vide."""
    out = []
    a = 0
    while a + echauffement + PURGE < n:
        d_test = a + echauffement + PURGE
        f_test = min(d_test + test, n)
        if f_test - d_test >= 20:      # une fenetre de test ridicule ne prouve rien
            out.append((a, d_test, f_test))
        a += pas
    return out


def executer(bars: list[dict], p: sg.Params, instrument: str, tf: str,
             echauffement: int = 400, test: int = 300,
             pas: int = 150) -> Resultat:
    """Deroule le protocole complet sur un historique de bougies."""
    r = Resultat(instrument=instrument, tf=tf)
    fs = fenetres(len(bars), echauffement, test, pas)
    r.fenetres = len(fs)
    if not fs:
        r.motif = f"historique trop court ({len(bars)} bougies)"
        return r

    tous_r: list[float] = []
    for a, d_test, f_test in fs:
        segment = bars[a:f_test]
        signaux = sg.detecter(segment, p)
        # PURGE : seuls les signaux nes DANS la fenetre de test comptent.
        seuil = d_test - a
        signaux = [s for s in signaux if s.index >= seuil]
        trades = sg.simuler(segment, signaux, p)
        trades = [t for t in trades if t.resultat in ("gagnant", "perdant")]
        if not trades:
            continue
        rs = [t.r_multiple for t in trades]
        if len(rs) >= TRADES_MIN_FENETRE:
            r.fenetres_evaluables += 1
            if sum(rs) > 0:
                r.fenetres_positives += 1
        tous_r.extend(rs)
        for t in trades:
            reg = _regime_a(segment, t.signal.index)
            r.regimes[reg] = r.regimes.get(reg, 0) + 1

    r.trades = len(tous_r)
    if r.trades:
        r.r_total = round(sum(tous_r), 2)
        r.r_moyen = round(sum(tous_r) / r.trades, 3)
        gains = sum(x for x in tous_r if x > 0)
        pertes = abs(sum(x for x in tous_r if x < 0))
        r.profit_factor = round(gains / pertes, 2) if pertes else float("inf")
        r.taux_reussite = round(100 * sum(1 for x in tous_r if x > 0) / r.trades, 1)
        cumul = sommet = creux = 0.0
        for x in tous_r:
            cumul += x
            sommet = max(sommet, cumul)
            creux = min(creux, cumul - sommet)
        r.pire_creux = round(creux, 2)

    # ---- verdict : cumulatif, un seul critere manquant = REFUSE ----------
    manques = []
    if r.trades < TRADES_MIN:
        manques.append(f"{r.trades} trades < {TRADES_MIN}")
    regimes_utiles = {k: v for k, v in r.regimes.items() if k != "indetermine"}
    if len(regimes_utiles) < REGIMES_MIN:
        manques.append(f"{len(regimes_utiles)} régime(s) couvert(s) < {REGIMES_MIN}")
    if r.profit_factor <= PF_MIN:
        manques.append(f"PF {r.profit_factor} ≤ {PF_MIN}")
    if r.r_moyen <= 0:
        manques.append(f"R moyen {r.r_moyen} ≤ 0")
    if r.fenetres_evaluables and \
            r.fenetres_positives / r.fenetres_evaluables < PART_FENETRES_POSITIVES:
        manques.append(f"{r.fenetres_positives}/{r.fenetres_evaluables} "
                       f"fenêtres évaluables positives")
    r.autorise = not manques
    r.motif = "tous les critères passés" if r.autorise else " · ".join(manques)
    return r


def ligne(r: Resultat) -> str:
    v = "✅ AUTORISÉ" if r.autorise else "❌ REFUSÉ"
    regs = ", ".join(f"{k} {v_}" for k, v_ in sorted(r.regimes.items()))
    return (f"| {r.instrument} | {r.tf} | {r.trades} | {r.r_moyen:+.3f} | "
            f"{r.r_total:+.2f} | {r.profit_factor} | {r.taux_reussite}% | "
            f"{r.pire_creux:+.2f} | {r.fenetres_positives}/{r.fenetres_evaluables} | "
            f"{regs} | {v} — {r.motif} |")
