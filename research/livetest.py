"""Le moteur de la grille de conviction — l'etat LIVE de chaque couple
(instrument × timeframe), calcule sur les signaux reellement emis et
resolus du journal, fenetre glissante de 90 jours.

Couleurs (SYSTEME_TRADING_SPEC §2) :
  VERT   R cumule > +0,3 ET PF > 1,3 ET >= 30 trades  -> a le droit d'emettre
  BLEU   edge positif mais echantillon court           -> observe
  GRIS   neutre, ou aucun trade resolu                 -> observe
  ROUGE  R cumule < 0                                  -> muet, reste teste

Le carreau change de couleur tout seul a mesure que les signaux se
resolvent : c'est le mecanisme de selection, pas une decoration.

Module pur : on lui passe les entrees du journal, aucun acces disque/reseau.
"""
from __future__ import annotations

import time

FENETRE_JOURS = 90
TRADES_MIN_VERT = 30
PF_MIN_VERT = 1.3
R_MIN_VERT = 0.3


def carreau(signaux: list[dict], tf: str, instrument: str | None = None,
            fenetre_jours: int = FENETRE_JOURS,
            maintenant: float | None = None) -> dict:
    """L'etat d'un couple (instrument × tf) sur la fenetre glissante."""
    if instrument is None:
        from gold_agent import instruments
        instrument = instruments.par_defaut().symbole
    depuis = (maintenant or time.time()) - fenetre_jours * 86400
    resolus = [s for s in signaux
               if s.get("tf") == tf and (s.get("cree_ts") or 0) >= depuis
               and s.get("statut") in ("gagnant", "perdant")
               and s.get("r_obtenu") is not None]
    rs = [float(s["r_obtenu"]) for s in resolus]
    n = len(rs)
    r_cumule = round(sum(rs), 2)
    gains = sum(x for x in rs if x > 0)
    pertes = abs(sum(x for x in rs if x < 0))
    pf = round(gains / pertes, 2) if pertes else (float("inf") if gains else 0.0)
    taux = round(100 * sum(1 for x in rs if x > 0) / n, 1) if n else 0.0

    if n and r_cumule > R_MIN_VERT and pf > PF_MIN_VERT and n >= TRADES_MIN_VERT:
        couleur = "vert"
    elif n and r_cumule > R_MIN_VERT:
        couleur = "bleu"          # edge positif, echantillon court
    elif n and r_cumule < 0:
        couleur = "rouge"
    else:
        couleur = "gris"

    return {"instrument": instrument, "tf": tf, "couleur": couleur,
            "trades": n, "r_cumule": r_cumule, "profit_factor": pf,
            "taux_reussite": taux, "fenetre_jours": fenetre_jours,
            "emission_grille": couleur == "vert"}


def grille(signaux: list[dict], tfs: list[str],
           instrument: str | None = None,
           maintenant: float | None = None) -> list[dict]:
    return [carreau(signaux, tf, instrument, maintenant=maintenant)
            for tf in tfs]
