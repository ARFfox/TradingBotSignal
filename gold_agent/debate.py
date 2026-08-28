"""Débat contradictoire haussier / baissier, avec garde-fou de risque.

Portage de l'architecture de TauricResearch/TradingAgents (Apache-2.0),
adaptée à l'or : la valeur de leur approche est structurelle, pas dans le
code. Deux thèses opposées sont construites SÉPARÉMENT à partir des mêmes
données, puis un garde-fou peut opposer son veto au camp gagnant.

Pourquoi séparer : un score unique masque les contre-arguments. Un prix en
tendance haussière ET en surachat extrême produit un score positif qui cache
que la moitié des éléments plaide pour attendre.
"""
from __future__ import annotations

from . import structure as st

# Le timeframe supérieur pèse plus lourd : un signal H1 ne renverse pas
# une structure Daily.
TF_WEIGHT = {"1D": 3.0, "H4": 2.0, "H1": 1.0, "M1": 0.0}


def _arg(side: str, tf: str, weight: float, text: str) -> dict:
    return {"camp": side, "timeframe": tf, "poids": round(weight, 1), "argument": text}


def build_cases(tf_results: list[dict], context: dict) -> dict:
    """Construit les deux thèses en parallèle, sans les compenser."""
    bull: list[dict] = []
    bear: list[dict] = []

    for tf in tf_results:
        label = tf["timeframe"]
        w = TF_WEIGHT.get(label, 1.0)
        if w == 0:
            continue  # timeframe d'execution : ne pese pas sur la direction
        i = tf["indicators"]
        price = tf["price"]
        trend = tf["trend_structure"]["trend"]
        pf, ps = tf.get("ema_periods", [50, 200])

        # --- Structure ---
        if trend == "haussier":
            bull.append(_arg("haussier", label, w * 2, "structure en sommets et creux ascendants"))
        elif trend == "baissier":
            bear.append(_arg("baissier", label, w * 2, "structure en sommets et creux descendants"))
        elif trend == "haussier_affaibli":
            bull.append(_arg("haussier", label, w * 0.5, "creux encore ascendants"))
            bear.append(_arg("baissier", label, w * 1.5, "sommets plafonnés — l'élan haussier bute"))
        elif trend == "baissier_affaibli":
            bear.append(_arg("baissier", label, w * 0.5, "sommets encore descendants"))
            bull.append(_arg("haussier", label, w * 1.5, "creux qui tiennent — la pression vendeuse faiblit"))

        # --- Tendance de fond ---
        if i["ema_slow"]:
            if price > i["ema_slow"]:
                bull.append(_arg("haussier", label, w * 2, f"prix au-dessus de l'EMA{ps} ({i['ema_slow']})"))
            else:
                bear.append(_arg("baissier", label, w * 2, f"prix sous l'EMA{ps} ({i['ema_slow']})"))
        if i["ema_fast"] and i["ema_slow"]:
            if i["ema_fast"] > i["ema_slow"]:
                bull.append(_arg("haussier", label, w * 1.5, f"EMA{pf} au-dessus de l'EMA{ps}"))
            else:
                bear.append(_arg("baissier", label, w * 1.5, f"EMA{pf} sous l'EMA{ps}"))

        # --- Momentum ---
        mh = i["macd_hist"]
        if mh is not None:
            side, lst = ("haussier", bull) if mh > 0 else ("baissier", bear)
            lst.append(_arg(side, label, w * 1.0, f"histogramme MACD {mh:+.2f}"))
        # La pente de l'histogramme doit se lire AVEC son signe : un
        # histogramme negatif qui remonte est une pression vendeuse qui
        # faiblit, donc un argument haussier — pas l'inverse.
        slope = tf.get("macd_slope")
        if mh is not None and slope in ("accelere", "s_essouffle"):
            monte = slope == "accelere"
            if mh > 0 and monte:
                bull.append(_arg("haussier", label, w * 1.0, "momentum haussier qui s'accélère"))
            elif mh > 0 and not monte:
                bear.append(_arg("baissier", label, w * 1.5, "momentum haussier qui s'essouffle"))
            elif mh < 0 and not monte:
                bear.append(_arg("baissier", label, w * 1.0, "momentum baissier qui s'accélère"))
            elif mh < 0 and monte:
                bull.append(_arg("haussier", label, w * 1.5, "momentum baissier qui s'essouffle"))

        # --- Force de tendance ---
        adx = i["adx14"]
        if adx is not None and adx >= 25:
            if trend.startswith("haussier"):
                bull.append(_arg("haussier", label, w * 1.5, f"tendance affirmée (ADX {adx})"))
            elif trend.startswith("baissier"):
                bear.append(_arg("baissier", label, w * 1.5, f"tendance affirmée (ADX {adx})"))

        # --- Exces ---
        rsi_v = i["rsi14"]
        if rsi_v is not None:
            if rsi_v >= 70:
                bear.append(_arg("baissier", label, w * 1.5,
                                 f"RSI {rsi_v} en surachat — peu de marge avant respiration"))
            elif rsi_v <= 30:
                bull.append(_arg("haussier", label, w * 1.5,
                                 f"RSI {rsi_v} en survente — peu de marge avant rebond"))
        if i["ema_fast"] and price:
            ecart = (price - i["ema_fast"]) / i["ema_fast"] * 100
            if ecart >= 5:
                bear.append(_arg("baissier", label, w * 2,
                                 f"prix à {ecart:+.1f}% de son EMA{pf} — extension, retour à la moyenne probable"))
            elif ecart <= -5:
                bull.append(_arg("haussier", label, w * 2,
                                 f"prix à {ecart:+.1f}% de son EMA{pf} — extension baissière, rebond probable"))

        # --- Divergences ---
        for d in tf.get("divergences", []):
            if d["type"] == "baissiere":
                bear.append(_arg("baissier", label, w * 2.5, f"divergence RSI baissière — {d['detail']}"))
            else:
                bull.append(_arg("haussier", label, w * 2.5, f"divergence RSI haussière — {d['detail']}"))

        # --- Niveaux proches ---
        atr = i["atr14"]
        if atr:
            for r in tf["levels"]["resistances"][:1]:
                if abs(r["price"] - price) <= atr:
                    bear.append(_arg("baissier", label, w * 1.0,
                                     f"résistance à {r['price']} à moins d'un ATR"))
            for s in tf["levels"]["supports"][:1]:
                if abs(price - s["price"]) <= atr:
                    bull.append(_arg("haussier", label, w * 1.0,
                                     f"support à {s['price']} à moins d'un ATR"))

    # --- Macro : l'or évolue à l'inverse du dollar ---
    dxy = context.get("TVC:DXY")
    if dxy and dxy.get("position"):
        if "sous" in dxy["position"]:
            bull.append(_arg("haussier", "macro", 2.0, "DXY sous son EMA50 — dollar faible, favorable à l'or"))
        else:
            bear.append(_arg("baissier", "macro", 2.0, "DXY au-dessus de son EMA50 — dollar ferme, défavorable à l'or"))

    bull.sort(key=lambda a: -a["poids"])
    bear.sort(key=lambda a: -a["poids"])
    return {"haussier": bull, "baissier": bear}


def risk_gate(cases: dict, tf_results: list[dict], synthese: dict) -> dict:
    """Le garde-fou. Peut opposer son veto au camp gagnant.

    Son rôle n'est pas de trancher la direction mais de dire si la
    configuration est exploitable. Une thèse juste dans un contexte
    inexploitable reste un mauvais moment pour agir.
    """
    poids_bull = sum(a["poids"] for a in cases["haussier"])
    poids_bear = sum(a["poids"] for a in cases["baissier"])
    total = poids_bull + poids_bear
    part_bull = (poids_bull / total * 100) if total else 50.0

    if part_bull >= 65:
        gagnant, conviction = "haussier", "nette"
    elif part_bull >= 55:
        gagnant, conviction = "haussier", "faible"
    elif part_bull <= 35:
        gagnant, conviction = "baissier", "nette"
    elif part_bull <= 45:
        gagnant, conviction = "baissier", "faible"
    else:
        gagnant, conviction = "indécis", "nulle"

    by_tf = {t["timeframe"]: t for t in tf_results}
    vetos: list[str] = []
    reserves: list[str] = []

    # 1. Conflit entre contexte et biais de session
    if synthese.get("verdict") == "CONFLIT DAILY / H4":
        vetos.append("Daily et H4 se contredisent — configuration à éviter, pas à arbitrer.")

    # 1b. Coherence avec la synthese : annoncer une "conviction nette" alors que
    # les timeframes ne s'alignent pas etait une contradiction interne.
    if synthese.get("verdict") == "MIXTE":
        reserves.append("Synthese MIXTE : les timeframes ne s'alignent pas — "
                        "la conviction affichee doit etre lue a la baisse.")

    # 2. Absence de tendance partout
    adxs = [t["indicators"]["adx14"] for t in tf_results if t["indicators"]["adx14"] is not None]
    if adxs and all(a < 20 for a in adxs):
        vetos.append("ADX sous 20 sur tous les timeframes — marché en range, les signaux de tendance ne valent rien.")

    # 3. Extension : score gradue, plus de seuil-falaise.
    # L'ancienne version exigeait RSI >= 70 ET ecart >= 5 %. Un RSI a 69,1
    # eteignait toute la protection alors que le prix restait etire a +7,3 %.
    for t in tf_results:
        if t.get("role") == "execution":
            continue  # le bruit M1 declencherait le veto en permanence
        ext = (t.get("regime") or {}).get("extension") or {}
        if ext.get("niveau") == "extreme":
            vetos.append(
                f"{t['timeframe']} : extension {ext['sens']} EXTREME (score {ext['score']}/100 — "
                f"RSI {ext['rsi']}, prix a {ext['ecart_pct']:+.1f}% de son EMA) — "
                f"entrer en continuation ici revient a acheter le haut.")
        elif ext.get("niveau") == "marquee":
            reserves.append(
                f"{t['timeframe']} : extension {ext['sens']} marquee (score {ext['score']}/100) — "
                f"un retour a la moyenne est statistiquement probable.")

    # 3b. Renversement recent : le prix a rendu son mouvement
    for t in tf_results:
        if t.get("role") == "execution":
            continue
        rev = (t.get("regime") or {}).get("renversement") or {}
        if rev.get("renversement") and rev["renversement"] != gagnant:
            reserves.append(f"{t['timeframe']} : {rev['note']} — contre la these {gagnant}.")

    # 3c. Expansion de volatilite : les stops calibres sur l'ATR sont perimes
    for t in tf_results:
        vol = (t.get("regime") or {}).get("volatilite") or {}
        if vol.get("regime") == "expansion_forte":
            reserves.append(
                f"{t['timeframe']} : ATR court a {vol['ratio']}x l'ATR long — {vol['note']}.")

    # 4. Divergence sur un timeframe majeur contre le camp gagnant
    for label in ("1D", "H4"):
        t = by_tf.get(label)
        if not t:
            continue
        for d in t.get("divergences", []):
            if (d["type"] == "baissiere" and gagnant == "haussier") or \
               (d["type"] == "haussiere" and gagnant == "baissier"):
                reserves.append(f"{label} : divergence RSI {d['type']} contre la thèse {gagnant}.")

    # 5. Stop structurel trop large pour être tenable
    h4 = by_tf.get("H4")
    inv = synthese.get("invalidation")
    if h4 and inv and h4["indicators"]["atr14"]:
        dist = abs(h4["price"] - inv["niveau"])
        en_atr = dist / h4["indicators"]["atr14"]
        if en_atr > 3:
            reserves.append(
                f"Invalidation à {en_atr:.1f} ATR H4 ({dist:.0f} points) — stop large, "
                f"la taille de position devra être réduite d'autant.")

    # 6. Unanimite : sur les marches, l'absence totale de contre-argument
    # signale plus souvent un angle mort qu'une certitude.
    if not cases["baissier"]:
        reserves.append("Aucun argument baissier identifié — unanimité suspecte, "
                        "vérifier ce que la lecture technique ignore (macro, événement, liquidité).")
    elif not cases["haussier"]:
        reserves.append("Aucun argument haussier identifié — unanimité suspecte, "
                        "vérifier ce que la lecture technique ignore (macro, événement, liquidité).")

    # 7. Conviction trop faible pour justifier une exposition
    if conviction in ("faible", "nulle") and not vetos:
        reserves.append(f"Répartition {part_bull:.0f}/{100-part_bull:.0f} — les deux thèses se valent presque.")

    if synthese.get("verdict") == "MIXTE" and conviction == "nette":
        conviction = "faible"

    if vetos:
        decision = "ABSTENTION"
        motif = "Le garde-fou oppose son veto : la configuration n'est pas exploitable."
    elif gagnant == "indécis":
        decision = "ABSTENTION"
        motif = "Aucun camp ne l'emporte."
    elif reserves:
        decision = f"BIAIS {gagnant.upper()} SOUS RÉSERVE"
        motif = "La thèse tient, mais des éléments imposent la prudence."
    else:
        decision = f"BIAIS {gagnant.upper()}"
        motif = f"Thèse {gagnant} avec conviction {conviction}, sans objection du garde-fou."

    return {
        "decision": decision,
        "motif": motif,
        "gagnant": gagnant,
        "conviction": conviction,
        "poids_haussier": round(poids_bull, 1),
        "poids_baissier": round(poids_bear, 1),
        "part_haussiere_pct": round(part_bull, 1),
        "vetos": vetos,
        "reserves": reserves,
    }
