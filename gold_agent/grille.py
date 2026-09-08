"""La grille de conviction cote serveur : etat live du journal
(fenetre 90 j, moteur research/livetest.py) enrichi du verdict
walk-forward persiste par research/rapport_edge.py.
"""
from __future__ import annotations


def grille_conviction(signaux: list, tf_noms: list[str]) -> list[dict]:
    """La grille de conviction : etat live 90 j (journal) + verdict
    walk-forward persiste par research/rapport_edge.py.

    La grille OBSERVE pour l'instant : elle ne gouverne pas encore
    l'emission (regle 3 du SYSTEME) — ce cablage attend la validation de
    Mushine, car il changerait quels timeframes notifient.
    """
    import json
    from pathlib import Path as _P
    try:
        from research import livetest
        carreaux = livetest.grille(signaux, tf_noms)
    except Exception:
        return []
    try:
        verdicts = json.loads((_P(__file__).resolve().parent.parent
                               / "research" / "verdicts.json").read_text())
    except Exception:
        verdicts = {}
    for x in carreaux:
        v = ((verdicts.get(x.get("instrument", "")) or verdicts) or {}).get(x["tf"]) or {}
        if not isinstance(v, dict) or "autorise" not in v:
            v = {}
        x["walkforward"] = ({"autorise": v.get("autorise"),
                             "r_moyen": v.get("r_moyen"),
                             "profit_factor": v.get("profit_factor"),
                             "trades": v.get("trades"),
                             "note": v.get("note", ""),
                             "genere_le": v.get("genere_le")}
                            if v else None)
    return carreaux
