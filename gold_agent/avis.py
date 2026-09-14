"""La calibration du Chef d'orchestre — les poids CALCULES, jamais choisis.

Principe (SPEC_V2 §4) : chaque signal emporte, au moment de son emission,
l'avis directionnel des agents qui en ont un. Quand le signal se resout
(gagnant/perdant), chaque avis devient un point de mesure :

    l'agent etait D'ACCORD avec le sens du signal et il a gagne  -> juste
    l'agent etait CONTRE le sens du signal et il a perdu         -> juste
    les deux autres cas                                          -> faux

L'exactitude par (agent, timeframe) donne le score de Brier (previsions
binaires : brier = 1 - exactitude) et le poids :

    poids = max(0.05, 2 x exactitude - 1)      — l'ecart au hasard.
    Un agent a 50 % (une piece) pese 0,05 ; a 75 %, 0,50 ; a 100 %, 1,00.

Sous AVIS_MIN avis resolus, le poids reste None : PAS de poids calcule sur
un echantillon qui ne prouve rien (regle : une base mince fait douter).

Module pur : on lui passe le paquet et les signaux du journal.
"""
from __future__ import annotations

AVIS_MIN = 10          # avis resolus exiges avant de calculer un poids
POIDS_PLANCHER = 0.05  # un agent nul devient quasi muet, jamais negatif


# --------------------------------------------------------------------------
# 1. Les avis du moment — quels agents ont une direction mesurable ?
# --------------------------------------------------------------------------
def directions(paquet: dict, r: dict) -> dict[str, str]:
    """{code agent: "achat"|"vente"} au moment de l'emission, pour le
    timeframe r. Un agent sans opinion ferme est ABSENT — le neutre ne
    s'enregistre pas, il ne prouverait rien.
    """
    out: dict[str, str] = {}

    # AG-02 Structure : la tendance du timeframe lui-meme
    t = str(r.get("tendance") or "")
    if t.startswith("haussi"):
        out["AG-02"] = "achat"
    elif t.startswith("baissi"):
        out["AG-02"] = "vente"

    # AG-01 Vigie (macro FRED) : le camp net des arguments taux/dollar
    ma = ((paquet.get("news") or {}).get("macro")) or {}
    args = ma.get("arguments") or []
    net = (sum(1 for a in args if a and a[0] == "haussier")
           - sum(1 for a in args if a and a[0] == "baissier"))
    if net > 0:
        out["AG-01"] = "achat"
    elif net < 0:
        out["AG-01"] = "vente"

    # AG-05 Minieres : AEM mene l'or (methode du projet) — avis seulement
    # si le mouvement des minieres est franc (> 1 %)
    mi = ((paquet.get("news") or {}).get("minieres")) or {}
    try:
        v = float((mi.get("aem") or {}).get("variation_pct"))
        if v > 1.0:
            out["AG-05"] = "achat"
        elif v < -1.0:
            out["AG-05"] = "vente"
    except (TypeError, ValueError):
        pass

    # AG-10 Miroir : le verdict intermarche, seulement quand la base est
    # fiable — une base mince ne peut ni confirmer ni contredire
    c = paquet.get("constellation") or {}
    sc = c.get("score") or {}
    sens_teste = c.get("sens_teste")
    if sc.get("fiable") and sens_teste in ("achat", "vente"):
        s = float(sc.get("score") or 0.0)
        if s > 0.15:
            out["AG-10"] = sens_teste
        elif s < -0.15:
            out["AG-10"] = "vente" if sens_teste == "achat" else "achat"

    # AG-13 Marche des matieres : la largeur (part de membres haussiers)
    for t_ in ((paquet.get("marches") or {}).get("tuiles")) or []:
        if t_.get("cle") == "matieres" and t_.get("fiable"):
            if t_["largeur"] >= 0.60:
                out["AG-13"] = "achat"
            elif t_["largeur"] <= 0.40:
                out["AG-13"] = "vente"
    return out


# --------------------------------------------------------------------------
# 2. La mesure — exactitude, Brier, poids par (agent, timeframe)
# --------------------------------------------------------------------------
def _juste(direction: str, sens: str, statut: str) -> bool:
    accord = direction == sens
    return (accord and statut == "gagnant") or (not accord and statut == "perdant")


def evaluer(signaux: list[dict]) -> dict:
    """{code: {"global": {...}, "par_tf": {tf: {...}}}} sur les signaux
    RESOLUS qui portent des avis. Chaque cellule : n, exactitude, brier,
    poids (None sous AVIS_MIN)."""
    brut: dict = {}
    for s in signaux:
        if s.get("statut") not in ("gagnant", "perdant"):
            continue
        avis = s.get("avis") or {}
        for code, direction in avis.items():
            if direction not in ("achat", "vente"):
                continue
            cle_tf = s.get("tf", "?")
            for portee in ("global", cle_tf):
                cell = brut.setdefault(code, {}).setdefault(portee, [0, 0])
                cell[0] += 1
                if _juste(direction, s.get("sens", ""), s["statut"]):
                    cell[1] += 1

    def _cellule(n: int, justes: int) -> dict:
        ex = round(justes / n, 3) if n else 0.0
        return {"n": n, "exactitude": ex, "brier": round(1 - ex, 3),
                "poids": (round(max(POIDS_PLANCHER, 2 * ex - 1), 2)
                          if n >= AVIS_MIN else None)}

    out: dict = {}
    for code, portees in brut.items():
        g = portees.pop("global", [0, 0])
        out[code] = {"global": _cellule(*g),
                     "par_tf": {tf: _cellule(*c) for tf, c in portees.items()}}
    return out


def resume(calibration: dict) -> list[str]:
    """Lignes lisibles pour la carte du Chef (AG-00)."""
    if not calibration:
        return ["calibration Brier : aucun avis résolu encore — "
                "chaque nouveau signal enregistre l'avis des agents"]
    lignes = []
    for code, c in sorted(calibration.items()):
        g = c["global"]
        if g["poids"] is None:
            lignes.append(f"{code} : {g['n']} avis résolus — poids par défaut "
                          f"(il en faut {AVIS_MIN})")
        else:
            lignes.append(f"{code} : exactitude {g['exactitude']:.0%} sur "
                          f"{g['n']} avis → poids calculé {g['poids']}")
    return lignes
