"""AG-19 Directeur — la direction exacte, décidée sur tout (étape 6bis).

Pont entre les données du site et `direction.py` (module livré) : il
traduit les sorties des agents en sources, laisse `decider()` trancher —
« INDÉTERMINÉE » est une réponse, pas une panne — et attache le verdict au
setup, point de bascule compris. Les poids viennent de `cerveau.json`
(source unique, étape 10.2) : tant qu'aucune source n'est mesurée, la
certitude reste plafonnée à 40 % par le module, et c'est voulu.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

CERVEAU_JSON = RACINE / "cerveau.json"
_CACHE: dict = {"t": 0.0, "poids": {}, "t_sens": 0.0, "sens": {}}


def poids_cerveau(famille: str) -> dict[str, float]:
    """Les poids d'une famille depuis cerveau.json — relus au plus toutes
    les 60 s. Vide tant que le cerveau n'a rien mesuré."""
    if time.time() - _CACHE["t"] > 60:
        try:
            _CACHE["poids"] = json.loads(CERVEAU_JSON.read_text()).get("poids", {})
        except Exception:
            _CACHE["poids"] = {}
        _CACHE["t"] = time.time()
    return {k: float(v) for k, v in (_CACHE["poids"].get(famille) or {}).items()}


def _memoire_couple(instrument: str, tf: str):
    """(sens_favorable, espérance, n) du couple — mesurés sur le journal,
    cache 300 s. Le sens favorable est celui des TP majoritaires : la
    mémoire dit où CE couple a gagné, pas où il devrait gagner."""
    if time.time() - _CACHE["t_sens"] > 300:
        table: dict = {}
        try:
            from .apprentissage import signaux
            for s in signaux():
                if s.statut not in ("TP", "SL"):
                    continue
                d = table.setdefault((s.instrument, s.tf),
                                     {"r": 0.0, "n": 0, "achat": 0, "vente": 0})
                d["r"] += s.r_realise or 0.0
                d["n"] += 1
                if s.statut == "TP":
                    d[s.sens] = d.get(s.sens, 0) + 1
        except Exception:
            table = {}
        _CACHE["sens"] = table
        _CACHE["t_sens"] = time.time()
    d = _CACHE["sens"].get((instrument, tf))
    if not d or not d["n"]:
        return None, None, 0
    sens = ("haussier" if d["achat"] > d["vente"]
            else "baissier" if d["vente"] > d["achat"] else "neutre")
    return sens, d["r"] / d["n"], d["n"]


def _regime_marche(marche: str) -> dict | None:
    try:
        from . import tableau
        etats = ((getattr(tableau, "DERNIER_PAQUET", None) or {})
                 .get("marches") or {}).get("etats") or {}
        e = etats.get(marche)
        if e and e.get("regime") in ("haussier", "baissier", "neutre"):
            return {"regime": e["regime"], "largeur": e.get("largeur", 0.5),
                    "nom": marche}
    except Exception:
        pass
    return None


def analyser(st: dict, r: dict, *, instrument: str, tf: str,
             marche: str = "matieres") -> None:
    """Attache `st["direction"]` au setup. Ne lève jamais : un Directeur en
    panne s'annonce dans le motif au lieu de casser l'émission."""
    try:
        from direction import decider, expliquer, sources_depuis_agents

        structure = None
        if r.get("prix") and r.get("ema_slow"):
            structure = {"ecart_ema": (r["prix"] - r["ema_slow"]) / r["ema_slow"]}
        momentum = {"rsi": r["rsi"]} if r.get("rsi") is not None else None
        sens_fav, esp, n = _memoire_couple(instrument, tf)
        memoire = ({"esperance": esp, "n": n, "sens_favorable": sens_fav}
                   if esp is not None else None)

        srcs = sources_depuis_agents(
            structure=structure,
            marche=_regime_marche(marche),
            intermarche=st.get("intermarche"),
            figures_biais=r.get("figures_biais"),
            momentum=momentum,
            memoire=memoire)
        d = decider(srcs, poids_cerveau("source"))
        st["direction"] = {
            "sens": d.sens, "score": d.score, "certitude": d.certitude,
            "base": round(d.base, 2), "accord": round(d.accord, 2),
            "bascule": d.bascule, "texte": expliquer(d),
            # la matière de direction.calibrer() au prochain cycle du cerveau
            "sources": [{"code": s.code, "sens": s.sens} for s in srcs],
        }
    except Exception as e:
        st["direction"] = {"sens": "INDÉTERMINÉE", "score": 0.0,
                           "certitude": 0.0, "base": 0.0, "accord": 0.0,
                           "bascule": "", "sources": [],
                           "texte": f"Directeur indisponible : {str(e)[:80]}"}
