"""Pont entre les setups du tableau et le débat AG-16/AG-18 (avocats.py).

APPLIQUER étape 6 : chaque signal passe au débat contradictoire AVANT
l'émission. Un verdict BLOQUÉ arrête le signal (motif visible) ; sinon le
facteur du débat multiplie la note du Superviseur — jamais au-dessus du
plafond. Le contexte est sérialisé dans le journal : c'est lui qui
permettra à `avocats.calibrer` de mesurer le poids réel de chaque argument.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace


def examiner_setup(st: dict, *, instrument: str, tf: str,
                   atr: float | None, spread: float | None,
                   intermarche: dict | None = None,
                   regime: str = "inconnu", leader: bool = False,
                   confluence: int = 1, news_dans_h: float | None = None,
                   carreau: dict | None = None,
                   poids: dict | None = None):
    """Fait plaider les deux avocats sur ce setup et APPLIQUE le verdict.

    Modifie `st` en place : `st["debat"]` (trace + contexte), et la note
    du Superviseur (`decision_chef`) multipliée par le facteur. Renvoie le
    Verdict — l'appelant décide quoi faire d'un BLOQUÉ.
    """
    from avocats import Contexte, debat

    s = SimpleNamespace(
        entree=st["entree"], sl=st["stop"], tp=st["objectif"],
        sens=st["setup"], tf=tf, instrument=instrument,
        rr=st.get("rr") or 0.0,
        note=(st.get("decision_chef") or {}).get("pct", 50) / 100.0)

    im = intermarche or {}
    n_combo = int((carreau or {}).get("trades") or 0)
    r_cum = (carreau or {}).get("r_cumule")
    esperance = (r_cum / n_combo) if (n_combo and r_cum is not None) else None
    ctx = Contexte(
        atr=atr or 0.0, spread=spread or 0.0,
        score_intermarche=im.get("score") or 0.0,
        base_intermarche=im.get("base") or 0.0,
        base_fiable=bool(im.get("fiable")),
        regime_marche=regime, instrument_leader=leader,
        confluence_tf=confluence, news_dans_h=news_dans_h,
        esperance_combo=esperance, n_combo=n_combo)

    v = debat(s, ctx, poids)

    st["debat"] = {
        "verdict": v.verdict, "score": v.score, "facteur": v.facteur,
        "explication": v.explication,
        "contre": [{"code": a.code, "texte": a.texte, "mesure": a.mesure}
                   for a in v.contre],
        "pour": [{"code": a.code, "texte": a.texte, "mesure": a.mesure}
                 for a in v.pour],
        # le contexte complet — la matière de calibrer() au prochain rapport
        "ctx": dataclasses.asdict(ctx),
    }

    dc = st.get("decision_chef")
    if dc and not v.bloque:
        from .decision import SEUIL_NOTIFICATION
        avant = dc["pct"]
        dc["pct"] = max(5, min(95, round(avant * v.facteur)))
        dc["notifiable"] = dc["pct"] >= SEUIL_NOTIFICATION
        dc.setdefault("composantes", []).append(
            f"débat {v.verdict} ×{v.facteur} ({avant}→{dc['pct']})")
    return v


def poids_arguments() -> dict[str, float]:
    """Les poids mesurés des arguments — depuis cerveau.json (étape 10.2 :
    LA source unique), avec repli sur l'ancien fichier du rapport quotidien.
    Vide tant que rien n'est mesuré — chaque argument vaut alors 1,0."""
    import json
    from pathlib import Path
    try:
        from .directeur import poids_cerveau
        p = poids_cerveau("argument")
        if p:
            return p
    except Exception:
        pass
    f = Path.home() / ".gold_agent_poids_avocats.json"
    if f.exists():
        try:
            return {k: float(v) for k, v in json.loads(f.read_text()).items()}
        except Exception:
            pass
    return {}
