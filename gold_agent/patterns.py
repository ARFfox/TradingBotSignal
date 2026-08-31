"""Structures de marché : zigzag, order blocks, sessions, vagues d'Elliott.

Toutes les détections sont déterministes et calculées depuis les bougies.
Aucune ne constitue une recommandation : ce sont des descriptions de ce que
le prix a fait.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence


# --------------------------------------------------------------------------
# ZIGZAG — la fondation : les jambes réelles du mouvement
# --------------------------------------------------------------------------

def _ajouter(points: list[dict], pt: dict) -> None:
    """Ajoute un point de zigzag en garantissant l'ALTERNANCE sommet/creux.

    Deux contraintes, toutes deux necessaires :
      - Jamais deux points du meme type a la suite : on garde le plus extreme.
      - Jamais deux points sur la meme bougie : une bougie de large amplitude
        peut marquer l'extreme d'une jambe et declencher le retournement de la
        suivante. On decale alors le second d'une bougie, plutot que de
        l'ecarter — l'ecarter romprait l'alternance et rendrait tout comptage
        d'Elliott impossible.
    """
    if not points:
        points.append(pt)
        return

    prec = points[-1]
    if pt["type"] == prec["type"]:
        plus_extreme = (pt["prix"] > prec["prix"]) if pt["type"] == "sommet" \
            else (pt["prix"] < prec["prix"])
        if plus_extreme:
            points[-1] = pt
        return

    if pt["index"] <= prec["index"]:
        pt = dict(pt, index=prec["index"] + 1)
    points.append(pt)


def zigzag(highs: Sequence[float], lows: Sequence[float],
           seuil: float) -> list[dict]:
    """Points de retournement séparés d'au moins `seuil` (en points de prix).

    Approche par seuil de renversement plutôt que par fractales : une jambe
    n'est validée que si le prix s'est retourné d'une amplitude significative,
    ce qui filtre le bruit sans dépendre d'une fenêtre arbitraire.
    """
    n = len(highs)
    if n < 3 or seuil <= 0:
        return []

    points: list[dict] = []
    # Amorçage : on cherche le premier mouvement dépassant le seuil
    ext_haut, ext_haut_i = highs[0], 0
    ext_bas, ext_bas_i = lows[0], 0
    direction: Optional[str] = None

    for i in range(1, n):
        if highs[i] > ext_haut:
            ext_haut, ext_haut_i = highs[i], i
        if lows[i] < ext_bas:
            ext_bas, ext_bas_i = lows[i], i

        if direction is None:
            if ext_haut - lows[i] >= seuil:
                direction = "bas"
                _ajouter(points, {"index": ext_haut_i, "prix": ext_haut, "type": "sommet"})
                ext_bas, ext_bas_i = lows[i], i
            elif highs[i] - ext_bas >= seuil:
                direction = "haut"
                _ajouter(points, {"index": ext_bas_i, "prix": ext_bas, "type": "creux"})
                ext_haut, ext_haut_i = highs[i], i
        elif direction == "haut":
            # On monte : on cherche un retournement baissier
            if ext_haut - lows[i] >= seuil:
                _ajouter(points, {"index": ext_haut_i, "prix": ext_haut, "type": "sommet"})
                direction = "bas"
                ext_bas, ext_bas_i = lows[i], i
        else:
            if highs[i] - ext_bas >= seuil:
                _ajouter(points, {"index": ext_bas_i, "prix": ext_bas, "type": "creux"})
                direction = "haut"
                ext_haut, ext_haut_i = highs[i], i

    # Jambe en cours, non confirmée
    if direction == "haut" and (not points or points[-1]["index"] != ext_haut_i):
        _ajouter(points, {"index": ext_haut_i, "prix": ext_haut, "type": "sommet", "en_cours": True})
    elif direction == "bas" and (not points or points[-1]["index"] != ext_bas_i):
        _ajouter(points, {"index": ext_bas_i, "prix": ext_bas, "type": "creux", "en_cours": True})

    for p in points:
        p["prix"] = round(p["prix"], 2)
    return points


def jambes(points: list[dict]) -> list[dict]:
    """Convertit les points de zigzag en jambes mesurées."""
    out = []
    for a, b in zip(points, points[1:]):
        amp = b["prix"] - a["prix"]
        out.append({
            "de": a["prix"], "vers": b["prix"],
            "sens": "hausse" if amp > 0 else "baisse",
            "amplitude": round(abs(amp), 2),
            "bougies": b["index"] - a["index"],
            "i_debut": a["index"], "i_fin": b["index"],
            "en_cours": b.get("en_cours", False),
        })
    return out


# --------------------------------------------------------------------------
# VAGUES D'ELLIOTT — comptage validé par les règles strictes
# --------------------------------------------------------------------------

def elliott(points: list[dict]) -> dict:
    """Tente d'étiqueter les 5 dernières jambes en impulsion 1-2-3-4-5.

    Les trois règles d'Elliott sont NON NÉGOCIABLES — un comptage qui en
    viole une est faux, pas approximatif :
      R1. La vague 2 ne retrace jamais plus de 100 % de la vague 1.
      R2. La vague 3 n'est jamais la plus courte des vagues 1, 3 et 5.
      R3. La vague 4 n'entre jamais dans le territoire de prix de la vague 1.

    Si une règle est violée, on ne renvoie pas de comptage. Le comptage
    automatique d'Elliott est intrinsèquement ambigu ; mieux vaut ne rien
    afficher qu'afficher une lecture fausse.
    """
    lgs = jambes(points)
    if len(lgs) < 5:
        return {"comptage": None, "raison": f"{len(lgs)} jambe(s) seulement, il en faut 5"}

    w = lgs[-5:]
    sens = w[0]["sens"]
    # Une impulsion alterne strictement
    attendu = [sens, "baisse" if sens == "hausse" else "hausse"] * 3
    if [j["sens"] for j in w] != attendu[:5]:
        return {"comptage": None, "raison": "les jambes n'alternent pas comme une impulsion"}

    w1, w2, w3, w4, w5 = w
    if any(j["bougies"] < 1 or j["amplitude"] <= 0 for j in w):
        return {"comptage": None, "raison": "jambe degeneree (0 bougie ou amplitude nulle)"}
    violations = []

    # R1
    if w2["amplitude"] > w1["amplitude"]:
        violations.append("R1 : la vague 2 retrace plus de 100 % de la vague 1")
    # R2
    if w3["amplitude"] < w1["amplitude"] and w3["amplitude"] < w5["amplitude"]:
        violations.append("R2 : la vague 3 est la plus courte")
    # R3 : chevauchement entre la fin de la vague 4 et le territoire de la vague 1
    if sens == "hausse":
        if w4["vers"] <= w1["vers"]:
            violations.append("R3 : la vague 4 entre dans le territoire de la vague 1")
    else:
        if w4["vers"] >= w1["vers"]:
            violations.append("R3 : la vague 4 entre dans le territoire de la vague 1")

    if violations:
        return {"comptage": None, "raison": "règles violées", "violations": violations}

    def ratio(a, b):
        return round(a["amplitude"] / b["amplitude"], 3) if b["amplitude"] else None

    return {
        "comptage": "impulsion",
        "direction": "haussière" if sens == "hausse" else "baissière",
        "vagues": [
            {"num": i + 1, "de": j["de"], "vers": j["vers"],
             "amplitude": j["amplitude"], "bougies": j["bougies"],
             "en_cours": j["en_cours"]}
            for i, j in enumerate(w)
        ],
        "ratios": {
            "w2_retrace_w1": ratio(w2, w1),
            "w3_extension_w1": ratio(w3, w1),
            "w4_retrace_w3": ratio(w4, w3),
            "w5_vs_w1": ratio(w5, w1),
        },
        "note": ("Comptage conforme aux trois règles strictes. Cela ne le rend pas "
                 "certain : plusieurs comptages valides coexistent souvent."),
    }


# --------------------------------------------------------------------------
# ORDER BLOCKS — dernière bougie opposée avant un mouvement impulsif
# --------------------------------------------------------------------------

def order_blocks(opens: Sequence[float], highs: Sequence[float],
                 lows: Sequence[float], closes: Sequence[float],
                 atr: float, seuil_impulsion: float = 2.0,
                 fenetre: int = 5, lookback: int = 150) -> list[dict]:
    """Order block = dernière bougie de sens opposé avant un déplacement.

    Un déplacement est retenu si le prix parcourt plus de `seuil_impulsion`
    ATR en `fenetre` bougies. La zone retenue est le corps de la bougie
    opposée (open-close), pas sa mèche.

    `mitige` indique si le prix est depuis revenu dans la zone.
    """
    n = len(closes)
    out: list[dict] = []
    debut = max(1, n - lookback)

    for i in range(debut, n - fenetre):
        deplacement_haut = max(highs[i + 1:i + 1 + fenetre]) - closes[i]
        deplacement_bas = closes[i] - min(lows[i + 1:i + 1 + fenetre])

        # OB haussier : bougie baissiere suivie d'un deplacement haussier
        if closes[i] < opens[i] and deplacement_haut >= atr * seuil_impulsion:
            out.append({"type": "haussier", "index": i,
                        "bas": min(opens[i], closes[i]), "haut": max(opens[i], closes[i]),
                        "impulsion_atr": round(deplacement_haut / atr, 2)})
        # OB baissier : bougie haussiere suivie d'un deplacement baissier
        elif closes[i] > opens[i] and deplacement_bas >= atr * seuil_impulsion:
            out.append({"type": "baissier", "index": i,
                        "bas": min(opens[i], closes[i]), "haut": max(opens[i], closes[i]),
                        "impulsion_atr": round(deplacement_bas / atr, 2)})

    # On ne garde que le dernier OB par grappe (les bougies consecutives
    # produisent des blocs quasi identiques)
    filtres: list[dict] = []
    for ob in out:
        if filtres and ob["index"] - filtres[-1]["index"] <= 2 and ob["type"] == filtres[-1]["type"]:
            filtres[-1] = ob
        else:
            filtres.append(ob)

    for ob in filtres:
        # Mitigation : le prix est-il revenu DANS la zone, corps compris ?
        # On mesure aussi la profondeur de penetration : un simple effleurement
        # du bord ne consomme pas un order block de la meme facon qu'un
        # retour au coeur de la zone.
        apres_bas = lows[ob["index"] + 1:]
        apres_haut = highs[ob["index"] + 1:]
        hauteur = max(ob["haut"] - ob["bas"], 1e-9)
        if ob["type"] == "haussier":
            penetration = (ob["haut"] - min(apres_bas)) if apres_bas else 0.0
        else:
            penetration = (max(apres_haut) - ob["bas"]) if apres_haut else 0.0
        ob["penetration_pct"] = round(max(0.0, min(100.0, penetration / hauteur * 100)), 1)
        # Un OB traverse de part en part n'est plus une zone de reaction :
        # il est casse. C'est different d'un simple retour dans la zone.
        if ob["type"] == "haussier":
            casse = bool(apres_bas) and min(apres_bas) < ob["bas"]
        else:
            casse = bool(apres_haut) and max(apres_haut) > ob["haut"]
        ob["casse"] = casse
        ob["mitige"] = ob["penetration_pct"] >= 50.0
        ob["etat"] = "casse" if casse else ("mitige" if ob["mitige"] else "actif")
        ob["age_bougies"] = n - 1 - ob["index"]
        ob["bas"], ob["haut"] = round(ob["bas"], 2), round(ob["haut"], 2)
        ob["milieu"] = round((ob["bas"] + ob["haut"]) / 2, 2)

    return filtres


# --------------------------------------------------------------------------
# SESSIONS — l'or ne se comporte pas pareil selon l'heure
# --------------------------------------------------------------------------

SESSIONS = {
    "Asie": (0, 8),
    "Londres": (8, 16),
    "New York": (13, 21),
}


def sessions(bars: list[dict], jours: int = 2) -> list[dict]:
    """Plage haute/basse de chaque séance, en UTC.

    Le chevauchement Londres/New York (13h-16h UTC) concentre l'essentiel du
    volume sur l'or — d'où le recouvrement volontaire des plages.
    """
    if not bars:
        return []

    par_jour: dict[str, dict[str, list]] = {}
    for b in bars:
        dt = datetime.fromtimestamp(b["time"], timezone.utc)
        jour = dt.strftime("%Y-%m-%d")
        for nom, (h0, h1) in SESSIONS.items():
            if h0 <= dt.hour < h1:
                par_jour.setdefault(jour, {}).setdefault(nom, []).append(b)

    out = []
    for jour in sorted(par_jour)[-jours:]:
        for nom in SESSIONS:
            bs = par_jour[jour].get(nom)
            if not bs:
                continue
            hi = max(x["high"] for x in bs)
            lo = min(x["low"] for x in bs)
            out.append({
                "jour": jour, "session": nom,
                "haut": round(hi, 2), "bas": round(lo, 2),
                "amplitude": round(hi - lo, 2),
                "bougies": len(bs),
                "debut": bs[0]["time"], "fin": bs[-1]["time"],
            })
    return out


def correction_abc(points: list[dict], atr: float) -> dict:
    """Scénario de correction A-B-C après une jambe impulsive.

    Lecture classique (celle des analystes Elliott) : après une chute
    impulsive A, un rebond partiel B (30 à 85 % de A), puis une jambe C
    qui projette environ la longueur de A depuis le sommet de B —
    le « mouvement mesuré ». Symétrique pour une correction haussière.

    Renvoie le stade du scénario et la cible projetée de C. C'est un
    SCÉNARIO, pas une prédiction : il est invalidé si B dépasse l'origine
    de A, et la cible est une zone (±0,5 ATR), pas un prix exact.
    """
    lgs = jambes(points)
    if len(lgs) < 2 or not atr:
        return {"scenario": None}

    def zone(v):
        return [round(v - atr * 0.5, 2), round(v + atr * 0.5, 2)]

    # Cas 1 : A vient de se terminer, B pas encore forme
    a = lgs[-1]
    if a["amplitude"] >= atr * 3 and not a["en_cours"]:
        pass  # traite via cas 2 quand B demarre

    # Cas 2 : A puis B en cours ou termine
    if len(lgs) >= 2:
        a, b = lgs[-2], lgs[-1]
        if a["amplitude"] >= atr * 3 and b["sens"] != a["sens"]:
            retrace = b["amplitude"] / a["amplitude"]
            if 0.25 <= retrace <= 0.90:
                cible_c = (b["vers"] - a["amplitude"]) if a["sens"] == "baisse" \
                    else (b["vers"] + a["amplitude"])
                return {"scenario": "correction ABC",
                        "stade": "B en cours" if b["en_cours"] else "B formee, C attendue",
                        "sens_correction": a["sens"],
                        "A": [a["de"], a["vers"]], "B_retrace_pct": round(retrace * 100),
                        "cible_C": round(cible_c, 2), "zone_C": zone(cible_c),
                        "invalidation": round(a["de"], 2),
                        "note": "scenario invalide si B depasse l'origine de A"}

    # Cas 3 : C en cours (A, B, puis C dans le sens de A)
    if len(lgs) >= 3:
        a, b, cj = lgs[-3], lgs[-2], lgs[-1]
        if a["amplitude"] >= atr * 3 and b["sens"] != a["sens"] \
                and cj["sens"] == a["sens"] and 0.25 <= b["amplitude"] / a["amplitude"] <= 0.90:
            cible_c = (b["vers"] - a["amplitude"]) if a["sens"] == "baisse" \
                else (b["vers"] + a["amplitude"])
            fait = cj["amplitude"] / a["amplitude"] * 100
            return {"scenario": "correction ABC", "stade": f"C en cours ({fait:.0f}% de A parcouru)",
                    "sens_correction": a["sens"],
                    "cible_C": round(cible_c, 2), "zone_C": zone(cible_c),
                    "invalidation": round(a["de"], 2),
                    "note": "scenario invalide si B depasse l'origine de A"}

    return {"scenario": None}
