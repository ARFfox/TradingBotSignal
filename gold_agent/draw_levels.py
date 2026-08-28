"""Trace sur TradingView les niveaux OBJECTIFS produits par l'analyse.

Ce module ne recommande aucune transaction. Il matérialise des faits :
pivots historiques ayant servi de support ou de résistance, niveau
d'invalidation de la thèse en cours, et largeur des zones dérivée de la
volatilité réelle (ATR).

Les identifiants des tracés créés sont enregistrés, pour pouvoir les
supprimer sans jamais toucher aux tracés de l'utilisateur.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import bridge

STATE = Path.home() / ".gold_agent_drawings.json"

TF_SECONDS = {"1D": 86400, "H4": 14400, "H1": 3600}

# TradingView attend backgroundColor pour le remplissage et color pour la
# bordure — surcharger seulement `color` laisse le fond violet par defaut.
ROUGE = {"color": "#ef5350", "backgroundColor": "rgba(239,83,80,0.10)",
         "textColor": "#ef5350", "linewidth": 1, "fillBackground": True, "transparency": 80}
VERT = {"color": "#26a69a", "backgroundColor": "rgba(38,166,154,0.10)",
        "textColor": "#26a69a", "linewidth": 1, "fillBackground": True, "transparency": 80}
ORANGE = {"color": "#ff9800", "backgroundColor": "rgba(255,152,0,0.16)",
          "textColor": "#ff9800", "linewidth": 2, "fillBackground": True, "transparency": 70}
# FVG : bleu pour les distinguer nettement des pivots support/resistance
BLEU = {"color": "#42a5f5", "backgroundColor": "rgba(66,165,245,0.14)",
        "textColor": "#42a5f5", "linewidth": 1, "fillBackground": True, "transparency": 75}
VIOLET = {"color": "#ab47bc", "backgroundColor": "rgba(171,71,188,0.14)",
          "textColor": "#ab47bc", "linewidth": 1, "fillBackground": True, "transparency": 75}
GRIS = {"color": "#78909c", "backgroundColor": "rgba(120,144,156,0.08)",
        "textColor": "#78909c", "linewidth": 1, "fillBackground": True, "transparency": 88}
TRAIT_ZZ = {"color": "#ffa726", "linewidth": 2, "linestyle": 0}
# Zones de setup : code couleur du tableau de bord d'une position
Z_ENTREE = {"color": "#2962ff", "backgroundColor": "rgba(41,98,255,0.18)",
            "textColor": "#2962ff", "linewidth": 2, "fillBackground": True, "transparency": 72}
Z_STOP = {"color": "#e53935", "backgroundColor": "rgba(229,57,53,0.20)",
          "textColor": "#e53935", "linewidth": 2, "fillBackground": True, "transparency": 70}
Z_OBJECTIF = {"color": "#00c853", "backgroundColor": "rgba(0,200,83,0.18)",
              "textColor": "#00c853", "linewidth": 2, "fillBackground": True, "transparency": 72}


def _load_ids() -> list[str]:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text()).get("ids", [])
        except Exception:
            return []
    return []


def _save_ids(ids: list[str]) -> None:
    STATE.write_text(json.dumps({"ids": ids}, indent=2))


def clear_mine() -> int:
    """Supprime uniquement les tracés créés par cet agent."""
    ids = _load_ids()
    removed = 0
    for eid in ids:
        try:
            bridge._run(["draw", "remove", eid])
            removed += 1
        except Exception:
            pass  # deja supprime a la main
    _save_ids([])
    return removed


def _zone(price: float, demi_largeur: float, t1: int, t2: int, style: dict) -> str | None:
    try:
        res = bridge._run([
            "draw", "shape", "-t", "rectangle",
            "-p", f"{price - demi_largeur:.2f}", "--price2", f"{price + demi_largeur:.2f}",
            "--time", str(t1), "--time2", str(t2),
            "--overrides", json.dumps(style),
        ])
        return res.get("entity_id")
    except Exception:
        return None


def _ligne(p1: float, t1: int, p2: float, t2: int, style: dict) -> str | None:
    try:
        res = bridge._run([
            "draw", "shape", "-t", "trend_line",
            "-p", f"{p1:.2f}", "--time", str(t1),
            "--price2", f"{p2:.2f}", "--time2", str(t2),
            "--overrides", json.dumps(style),
        ])
        return res.get("entity_id")
    except Exception:
        return None


def _label(price: float, t: int, texte: str, style: dict) -> str | None:
    try:
        res = bridge._run([
            "draw", "shape", "-t", "text", "-p", f"{price:.2f}", "--time", str(t),
            "--text", texte, "--overrides", json.dumps(style),
        ])
        return res.get("entity_id")
    except Exception:
        return None


def draw(rep: dict, timeframes: tuple = ("1D", "H4"), remplacer: bool = True,
         portee_atr: float | None = None) -> dict:
    """Trace les zones issues du rapport d'analyse.

    Largeur de zone = 0,5 x ATR du timeframe d'origine. Un niveau n'est pas
    un prix exact : c'est une aire dont l'épaisseur reflète la volatilité.
    """
    by_tf = {t["timeframe"]: t for t in rep["timeframes"]}
    ref = by_tf.get("H4") or rep["timeframes"][0]

    # Fenêtre temporelle : on remonte 40 bougies et on prolonge 15 vers la droite
    last_t = ref.get("last_bar_time")
    if not last_t:
        raise RuntimeError("horodatage de la dernière bougie absent du rapport")
    step = TF_SECONDS.get(ref["timeframe"], 14400)
    t1, t2 = last_t - step * 40, last_t + step * 15

    # Portee du trace : sur un graphique M1, une zone Daily a 150 points ecrase
    # l'echelle et rend les FVG (0,5 pt de large) invisibles. On limite donc le
    # trace a ce qui est atteignable a l'horizon du timeframe d'execution.
    prix_actuel = ref["price"]
    exec_tf_pre = next((t for t in rep["timeframes"] if t.get("role") == "execution"), None)
    portee = None
    if portee_atr is None and exec_tf_pre:
        atr_exec = exec_tf_pre["indicators"].get("atr14")
        if atr_exec:
            portee = atr_exec * 30
    elif portee_atr is not None:
        portee = portee_atr

    if remplacer:
        clear_mine()

    hors_portee = 0

    ids: list[str] = []
    traces: list[dict] = []
    deja: list[float] = []

    # Une largeur de reference unique (ATR H4) plutot que l'ATR de chaque
    # timeframe : sinon les zones Daily, larges de ~1 ATR journalier, se
    # fondent en un seul bloc illisible.
    atr_ref = ref["indicators"].get("atr14")
    if not atr_ref:
        raise RuntimeError("ATR H4 indisponible — impossible de dimensionner les zones")
    demi = atr_ref * 0.5
    if portee is not None:
        # A l'echelle M1, une zone large d'un demi-ATR H4 (18 pts) couvre tout
        # l'ecran. On la ramene a l'echelle du timeframe d'execution.
        demi = min(demi, (exec_tf_pre["indicators"]["atr14"] or 1) * 1.5)

    for label in timeframes:
        tf = by_tf.get(label)
        if not tf:
            continue

        for genre, niveaux, style in (
            ("resistance", tf["levels"]["resistances"], ROUGE),
            ("support", tf["levels"]["supports"], VERT),
        ):
            for n in niveaux:
                prix = n["price"]
                # Evite de superposer deux zones quasi identiques
                if portee is not None and abs(prix - prix_actuel) > portee:
                    hors_portee += 1
                    continue
                if any(abs(prix - d) < demi * 2.5 for d in deja):
                    continue
                deja.append(prix)
                eid = _zone(prix, demi, t1, t2, style)
                if eid:
                    ids.append(eid)
                    lid = _label(prix + demi, t2, f"{genre} {label} {prix:.0f} ({n['touches']}x)", style)
                    if lid:
                        ids.append(lid)
                    traces.append({"genre": genre, "timeframe": label, "prix": prix,
                                   "zone": [round(prix - demi, 2), round(prix + demi, 2)],
                                   "touches": n["touches"]})

    # FVG du timeframe d'execution : zones de desequilibre non comblees.
    # Bornes reelles du gap, pas une largeur derivee de l'ATR.
    exec_tf = exec_tf_pre
    if exec_tf and exec_tf.get("fvg"):
        step_x = TF_SECONDS.get("H1", 3600)
        for g in exec_tf["fvg"]:
            centre = (g["bas"] + g["haut"]) / 2
            demi_g = (g["haut"] - g["bas"]) / 2
            eid = _zone(centre, demi_g, last_t - step_x * 3, t2, BLEU)
            if eid:
                ids.append(eid)
                lid = _label(g["haut"], t2, f"FVG {g['type'][:4]} {g['bas']:.1f}-{g['haut']:.1f}", BLEU)
                if lid:
                    ids.append(lid)
                traces.append({"genre": f"FVG {g['type']}", "timeframe": exec_tf["timeframe"],
                               "prix": g["milieu"], "zone": [g["bas"], g["haut"]],
                               "touches": 0, "distance": g["distance"]})

    # Motifs du timeframe d'execution : zigzag, order blocks, Elliott
    src = exec_tf or by_tf.get("H1")
    mo = (src or {}).get("motifs") or {}
    if src and mo:
        pas = TF_SECONDS.get(src["timeframe"], 3600)
        t_dernier = src.get("last_bar_time") or last_t
        n_bougies = src.get("bars_used", 300)

        def t_de(idx: int) -> int:
            return t_dernier - (n_bougies - 1 - idx) * pas

        # Zigzag : les jambes reelles du mouvement
        zz = mo.get("zigzag") or []
        for a, b in zip(zz, zz[1:]):
            eid = _ligne(a["prix"], t_de(a["index"]), b["prix"], t_de(b["index"]), TRAIT_ZZ)
            if eid:
                ids.append(eid)
        if zz:
            traces.append({"genre": "zigzag", "timeframe": src["timeframe"],
                           "prix": zz[-1]["prix"], "zone": [zz[0]["prix"], zz[-1]["prix"]],
                           "touches": len(zz)})

        # Etiquettes Elliott, uniquement si le comptage est valide
        el = mo.get("elliott") or {}
        if el.get("comptage"):
            for v, pt in zip(el["vagues"], zz[-6:]):
                lid = _label(v["vers"], t_de(pt["index"]), f"({v['num']})", TRAIT_ZZ)
                if lid:
                    ids.append(lid)

        # Order blocks exploitables
        for ob in mo.get("order_blocks") or []:
            centre = (ob["bas"] + ob["haut"]) / 2
            demi_ob = max((ob["haut"] - ob["bas"]) / 2, 0.05)
            eid = _zone(centre, demi_ob, t_de(ob["index"]), t2, VIOLET)
            if eid:
                ids.append(eid)
                lid = _label(ob["haut"], t2, f"OB {ob['type'][:4]} {ob['bas']:.1f}", VIOLET)
                if lid:
                    ids.append(lid)
                traces.append({"genre": f"OB {ob['type']}", "timeframe": src["timeframe"],
                               "prix": ob["milieu"], "zone": [ob["bas"], ob["haut"]],
                               "touches": 0})

    # Sessions : plages horaires, tracees depuis le H1
    h1 = by_tf.get("H1")
    ses = ((h1 or {}).get("motifs") or {}).get("sessions") or []
    for x in ses[-3:]:
        if portee is not None and abs((x["haut"] + x["bas"]) / 2 - prix_actuel) > portee * 2:
            continue
        centre = (x["haut"] + x["bas"]) / 2
        eid = _zone(centre, (x["haut"] - x["bas"]) / 2, x["debut"], x["fin"], GRIS)
        if eid:
            ids.append(eid)
            lid = _label(x["haut"], x["fin"], f"{x['session']} {x['jour'][5:]}", GRIS)
            if lid:
                ids.append(lid)
            traces.append({"genre": f"session {x['session']}", "timeframe": "H1",
                           "prix": round(centre, 2), "zone": [x["bas"], x["haut"]], "touches": 0})

    # Niveau d'invalidation de la thèse en cours — le fait le plus actionnable
    inv = (rep.get("synthese") or {}).get("invalidation")
    if inv and (portee is None or abs(inv["niveau"] - prix_actuel) <= portee):
        eid = _zone(inv["niveau"], demi * 0.6, t1, t2, ORANGE)
        if eid:
            ids.append(eid)
            lid = _label(inv["niveau"] - demi * 1.2, t2, f"INVALIDATION {inv['niveau']:.0f}", ORANGE)
            if lid:
                ids.append(lid)
            traces.append({"genre": "invalidation", "timeframe": "H4",
                           "prix": inv["niveau"], "sens": inv["sens"]})

    _save_ids(ids)
    return {"traces": traces, "nb_objets": len(ids), "atr_h4": ref["indicators"].get("atr14"),
            "portee": round(portee, 1) if portee else None, "hors_portee": hors_portee}


def draw_setup(setup: dict, last_bar_time: int, pas_secondes: int,
               bougies_avant: int = 60, bougies_apres: int = 25,
               remplacer: bool = True) -> dict:
    """Trace les trois zones du setup produit par la règle mécanique.

    Ce n'est pas une recommandation : c'est la sortie de `strategy.setup_actuel`,
    dont `gold_agent.backtest` mesure la valeur historique. Les niveaux ne
    relèvent d'aucun jugement — ils découlent des paramètres de la règle.
    """
    if not setup.get("setup"):
        return {"traces": [], "nb_objets": 0, "raison": setup.get("raison")}

    if remplacer:
        clear_mine()

    t1 = last_bar_time - pas_secondes * bougies_avant
    t2 = last_bar_time + pas_secondes * bougies_apres

    ids: list[str] = []
    traces: list[dict] = []

    for cle, libelle, style in (
        ("entree_zone", "ENTREE", Z_ENTREE),
        ("stop_zone", "STOP", Z_STOP),
        ("objectif_zone", "OBJECTIF", Z_OBJECTIF),
    ):
        bas, haut = setup[cle]
        centre, demi = (bas + haut) / 2, max((haut - bas) / 2, 0.05)
        eid = _zone(centre, demi, t1, t2, style)
        if eid:
            ids.append(eid)
            base = setup[cle.replace("_zone", "")]
            txt = f"{libelle} {base}"
            if libelle == "OBJECTIF":
                txt += f"  (R:R {setup['rr']})"
            elif libelle == "STOP":
                txt += f"  (-{setup['risque_pts']} pts)"
            lid = _label(haut, t2, txt, style)
            if lid:
                ids.append(lid)
            traces.append({"genre": libelle.lower(), "prix": base, "zone": [bas, haut]})

    _save_ids(ids)
    return {"traces": traces, "nb_objets": len(ids), "sens": setup["setup"],
            "declenche": setup["declenche"], "rr": setup["rr"]}
