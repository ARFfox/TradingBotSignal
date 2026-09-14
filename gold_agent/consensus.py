"""Le consensus pondere — la boule du site.

Chaque element vote avec un poids, rien n'est compense en silence, et
la liste des contributions est renvoyee pour que la boule soit
VERIFIABLE — un consensus qu'on ne peut pas decomposer est un chiffre
de marketing. Separe de cerveau.py (regle 17).
"""
from __future__ import annotations


# Poids par timeframe pour le consensus : le H4 pese plus que le M15,
# comme dans le module de debat (un signal court ne renverse pas une
# structure longue).
POIDS_TF = {"H4": 3.0, "H1": 2.0, "M30": 1.0, "M15": 0.5, "M5": 0.25}


def _consensus(resultats: list, macro: dict, minieres: dict, cot: dict,
               saison: dict | None = None) -> dict:
    """Agrège toutes les couches en une répartition haussier/baissier.

    Même logique que le débat contradictoire : chaque élément vote avec un
    poids, rien n'est compensé silencieusement. La liste des contributions
    est renvoyée pour que la boule soit VÉRIFIABLE — un consensus qu'on ne
    peut pas décomposer est un chiffre de marketing.
    """
    contributions = []

    def voter(camp, poids, source):
        contributions.append({"camp": camp, "poids": round(poids, 1), "source": source})

    for r in resultats:
        w = POIDS_TF.get(r["nom"], 1.0)
        ef, es, rsi = r.get("ema_fast"), r.get("ema_slow"), r.get("rsi")
        prix = r.get("prix")
        if ef and es:
            voter("haussier" if ef > es else "baissier", w * 1.5,
                  f"{r['nom']} : EMA rapide {'>' if ef > es else '<'} lente")
        if prix and es:
            voter("haussier" if prix > es else "baissier", w * 1.0,
                  f"{r['nom']} : prix {'au-dessus' if prix > es else 'sous'} EMA lente")
        if rsi is not None:
            if rsi >= 55:
                voter("haussier", w * 0.5, f"{r['nom']} : RSI {rsi:.0f}")
            elif rsi <= 45:
                voter("baissier", w * 0.5, f"{r['nom']} : RSI {rsi:.0f}")
        setup = r.get("setup") or {}
        if setup.get("setup"):
            voter("haussier" if setup["setup"] == "achat" else "baissier",
                  w * 1.0, f"{r['nom']} : signal {setup['setup']} actif")

    for src in (macro, minieres, cot, saison):
        for camp, poids, txt in (src or {}).get("arguments", []):
            voter(camp, poids, txt.split(" — ")[0][:60])

    p_h = sum(c["poids"] for c in contributions if c["camp"] == "haussier")
    p_b = sum(c["poids"] for c in contributions if c["camp"] == "baissier")
    total = p_h + p_b
    pct = round(p_h / total * 100, 1) if total else 50.0
    if pct >= 65:
        verdict = "HAUSSIER"
    elif pct <= 35:
        verdict = "BAISSIER"
    else:
        verdict = "PARTAGÉ"
    contributions.sort(key=lambda c: -c["poids"])
    return {"haussier": round(p_h, 1), "baissier": round(p_b, 1),
            "pct_haussier": pct, "verdict": verdict,
            "nb_haussier": sum(1 for c in contributions if c["camp"] == "haussier"),
            "nb_baissier": sum(1 for c in contributions if c["camp"] == "baissier"),
            "contributions": contributions[:14]}


