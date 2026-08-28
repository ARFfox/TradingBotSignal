"""Moteur d'analyse multi-timeframe pour l'or.

Principe : le timeframe supérieur donne le contexte, l'inférieur le timing.
Un signal H1 qui contredit la structure Daily n'est pas un signal.

ANALYSE UNIQUEMENT — ne produit aucun ordre et ne constitue pas un conseil
en investissement.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import bridge, debate, indicators as ind, patterns as pat, regime as rg, structure as st

# Les periodes d'EMA sont adaptees au timeframe : sur 300 bougies M1 (6h de
# donnees), une "EMA200" ne couvre que 3h — l'appeler tendance de fond serait
# un abus. Le contexte vient des timeframes superieurs, le M1 ne fait que le
# timing.
TIMEFRAMES = [
    {"label": "1D", "tf": "D", "role": "contexte", "ema": (50, 200)},
    {"label": "H4", "tf": "240", "role": "biais", "ema": (50, 200)},
    {"label": "H1", "tf": "60", "role": "timing", "ema": (50, 200), "motifs": True},
]

# Profil intraday : ajoute le M1 avec des periodes courtes et la detection FVG.
TIMEFRAMES_M1 = TIMEFRAMES + [
    {"label": "M1", "tf": "1", "role": "execution", "ema": (20, 50), "motifs": True},
]
GOLD = "FOREXCOM:XAUUSD"


def analyze_timeframe(bars: list[dict], label: str, role: str,
                     ema_periods: tuple = (50, 200), detect_fvg: bool = False,
                     detect_patterns: bool = False) -> dict:
    o = [b["open"] for b in bars]
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    price = c[-1]

    p_fast, p_slow = ema_periods
    ema_fast = ind.last_valid(ind.ema(c, p_fast))
    ema_slow = ind.last_valid(ind.ema(c, p_slow))
    rsi_series = ind.rsi(c, 14)
    rsi14 = ind.last_valid(rsi_series)
    atr14 = ind.last_valid(ind.atr(h, l, c, 14))
    macd_d = ind.macd(c)
    macd_hist = ind.last_valid(macd_d["histogram"])
    adx_d = ind.adx(h, l, c, 14)
    adx_val = ind.last_valid(adx_d["adx"])

    piv_span = 2 if label in ("M1", "M5") else 3
    piv = st.pivots(h, l, left=piv_span, right=piv_span)
    trend = st.trend_from_structure(piv)
    divergences = st.rsi_divergence(piv, rsi_series)
    macd_slope = st.momentum_slope(macd_d["histogram"])
    levels = st.key_levels(piv, price, atr14)
    rng = st.swing_range(h, l, lookback=50)

    # Score directionnel : chaque critere vaut +1 (haussier) ou -1 (baissier).
    signals = []
    score = 0
    if ema_fast is not None:
        up = price > ema_fast
        score += 1 if up else -1
        signals.append(f"prix {'au-dessus' if up else 'sous'} EMA{p_fast} ({ema_fast:.2f})")
    if ema_slow is not None:
        up = price > ema_slow
        score += 1 if up else -1
        signals.append(f"prix {'au-dessus' if up else 'sous'} EMA{p_slow} ({ema_slow:.2f})")
    if ema_fast is not None and ema_slow is not None:
        up = ema_fast > ema_slow
        score += 1 if up else -1
        signals.append(f"EMA{p_fast} {'>' if up else '<'} EMA{p_slow}")
    if macd_hist is not None:
        up = macd_hist > 0
        score += 1 if up else -1
        signals.append(f"histogramme MACD {'positif' if up else 'negatif'} ({macd_hist:+.2f})")
    if trend["trend"].startswith("haussier"):
        score += 1
        signals.append(f"structure {trend['trend']}")
    elif trend["trend"].startswith("baissier"):
        score -= 1
        signals.append(f"structure {trend['trend']}")
    else:
        signals.append(f"structure {trend['trend']}")

    if score >= 3:
        bias = "haussier"
    elif score <= -3:
        bias = "baissier"
    elif score >= 1:
        bias = "haussier_faible"
    elif score <= -1:
        bias = "baissier_faible"
    else:
        bias = "neutre"

    # ADX qualifie la FORCE, pas la direction.
    if adx_val is None:
        force = "inconnue"
    elif adx_val >= 25:
        force = "tendance affirmee"
    elif adx_val >= 20:
        force = "tendance naissante"
    else:
        force = "sans tendance (range)"

    gaps = []
    if detect_fvg and atr14:
        # Filtre a 0,3 ATR : en dessous, c'est du bruit de marche
        tous = st.fair_value_gaps(o, h, l, c, min_size=atr14 * 0.3, lookback=200)
        gaps = st.fvg_actifs(tous, price)

    motifs = {}
    if detect_patterns and atr14:
        zz = pat.zigzag(h, l, seuil=atr14 * 2.0)
        obs = pat.order_blocks(o, h, l, c, atr=atr14)
        motifs = {
            "zigzag": zz[-12:],
            "jambes": pat.jambes(zz)[-6:],
            "elliott": pat.elliott(zz),
            "order_blocks": [x for x in obs if x["etat"] != "casse"][-5:],
            "order_blocks_total": len(obs),
            "order_blocks_casses": sum(1 for x in obs if x["etat"] == "casse"),
            "sessions": pat.sessions(bars, jours=3) if label in ("H1", "H4") else [],
        }

    return {
        "timeframe": label,
        "role": role,
        "ema_periods": list(ema_periods),
        "fvg": gaps,
        "motifs": motifs,
        "price": round(price, 2),
        "bias": bias,
        "score": score,
        "signals": signals,
        "trend_structure": trend,
        "force": force,
        "indicators": {
            "ema_fast": round(ema_fast, 2) if ema_fast else None,
            "ema_slow": round(ema_slow, 2) if ema_slow else None,
            "rsi14": round(rsi14, 1) if rsi14 else None,
            "atr14": round(atr14, 2) if atr14 else None,
            "adx14": round(adx_val, 1) if adx_val else None,
            "macd_hist": round(macd_hist, 2) if macd_hist else None,
        },
        "last_bar_time": bars[-1].get("time"),
        "regime": {
            "volatilite": rg.regime_volatilite(h, l, c),
            "renversement": rg.renversement(o, h, l, c),
            "extension": rg.score_extension(price, ema_fast, rsi14),
        },
        "divergences": divergences,
        "macd_slope": macd_slope,
        "levels": levels,
        "range_50": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in rng.items()},
        "bars_used": len(bars),
    }


def _rank(bias: str) -> int:
    return {
        "haussier": 2, "haussier_faible": 1, "neutre": 0,
        "baissier_faible": -1, "baissier": -2,
    }.get(bias, 0)


def combine(tf_results: list[dict]) -> dict:
    by_tf = {r["timeframe"]: r for r in tf_results}
    d, h4, h1 = by_tf.get("1D"), by_tf.get("H4"), by_tf.get("H1")

    ranks = {k: _rank(v["bias"]) for k, v in by_tf.items()}
    aligned = len({1 if r > 0 else (-1 if r < 0 else 0) for r in ranks.values()}) == 1

    if aligned and all(r > 0 for r in ranks.values()):
        verdict = "ALIGNEMENT HAUSSIER"
        detail = "Les trois timeframes pointent dans le meme sens. Contexte le plus lisible."
    elif aligned and all(r < 0 for r in ranks.values()):
        verdict = "ALIGNEMENT BAISSIER"
        detail = "Les trois timeframes pointent dans le meme sens. Contexte le plus lisible."
    elif d and h4 and (_rank(d["bias"]) > 0) != (_rank(h4["bias"]) > 0) and ranks.get("1D", 0) != 0 and ranks.get("H4", 0) != 0:
        verdict = "CONFLIT DAILY / H4"
        detail = ("Le contexte de fond et le biais de session se contredisent. "
                  "Situation la plus couteuse historiquement — priorite au Daily ou abstention.")
    else:
        verdict = "MIXTE"
        detail = "Pas d'alignement franc. Le timeframe superieur garde la priorite."

    # Invalidation : le niveau qui casse la lecture, tire du H4.
    invalidation = None
    if h4:
        lv = h4["levels"]
        if _rank(h4["bias"]) > 0 and lv["supports"]:
            invalidation = {"niveau": lv["supports"][0]["price"], "sens": "sous ce support, le biais haussier tombe"}
        elif _rank(h4["bias"]) < 0 and lv["resistances"]:
            invalidation = {"niveau": lv["resistances"][0]["price"], "sens": "au-dessus de cette resistance, le biais baissier tombe"}

    # Extension : une tendance alignee mais surchauffee est le piege classique.
    # On la signale explicitement plutot que de vendre un faux confort.
    alertes = []
    for tf in tf_results:
        i = tf["indicators"]
        rsi_v, ema50_v, price_v = i.get("rsi14"), i.get("ema_fast"), tf["price"]
        if rsi_v is not None and rsi_v >= 70:
            alertes.append(f"{tf['timeframe']} : RSI {rsi_v} en zone de surachat")
        elif rsi_v is not None and rsi_v <= 30:
            alertes.append(f"{tf['timeframe']} : RSI {rsi_v} en zone de survente")
        if ema50_v and price_v:
            ecart = (price_v - ema50_v) / ema50_v * 100
            if abs(ecart) >= 5:
                alertes.append(
                    f"{tf['timeframe']} : prix a {ecart:+.1f}% de son EMA50 — extension marquee, "
                    f"un retour a la moyenne est statistiquement probable")

    if alertes and aligned:
        detail += (" Attention : la tendance est alignee mais etiree — "
                   "poursuivre ici revient a entrer au plus haut du mouvement.")

    return {"verdict": verdict, "detail": detail, "alignement": aligned,
            "rangs": ranks, "invalidation": invalidation, "alertes_extension": alertes}


def run(symbol: str = GOLD, bars_count: int = 300, context_symbols: tuple = ("TVC:DXY",),
        timeframes: list | None = None) -> dict:
    bridge.ensure_tradingview()
    original = None
    try:
        original = bridge.status()
    except Exception:
        pass

    tf_results, errors = [], []
    for spec in (timeframes or TIMEFRAMES):
        label = spec["label"]
        try:
            data = bridge.fetch_timeframe(symbol, spec["tf"], bars_count)
            tf_results.append(analyze_timeframe(
                data["bars"], label, spec["role"],
                ema_periods=spec.get("ema", (50, 200)),
                detect_fvg=spec.get("role") == "execution",
                detect_patterns=spec.get("motifs", False),
            ))
        except Exception as e:
            errors.append(f"{label}: {e}")

    if not tf_results:
        raise RuntimeError("Aucun timeframe analysable. Erreurs: " + "; ".join(errors))

    context = {}
    for cs in context_symbols:
        try:
            data = bridge.fetch_timeframe(cs, "D", 250)
            c = [b["close"] for b in data["bars"]]
            e50 = ind.last_valid(ind.ema(c, 50))
            context[cs] = {
                "close": round(c[-1], 3),
                "ema_fast": round(e50, 3) if e50 else None,
                "position": ("au-dessus EMA50" if e50 and c[-1] > e50 else "sous EMA50") if e50 else None,
                "variation_5j_pct": round((c[-1] - c[-6]) / c[-6] * 100, 2) if len(c) > 6 else None,
            }
        except Exception as e:
            errors.append(f"contexte {cs}: {e}")

    # Restauration de l'etat initial du graphique
    if original and original.get("chart_symbol"):
        try:
            bridge.set_symbol(original["chart_symbol"], settle=0.5)
            if original.get("chart_resolution"):
                bridge.set_timeframe(original["chart_resolution"], settle=0.5)
        except Exception:
            pass

    synthese = combine(tf_results)
    _sauver_dernier = True
    cases = debate.build_cases(tf_results, context)
    gate = debate.risk_gate(cases, tf_results, synthese)

    return {
        "symbol": symbol,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timeframes": tf_results,
        "synthese": synthese,
        "debat": cases,
        "garde_fou": gate,
        "contexte_macro": context,
        "erreurs": errors,
        "avertissement": ("Analyse technique automatisee. Ne constitue pas un conseil en "
                          "investissement. Aucun ordre n'est passe. Les decisions restent "
                          "celles de l'operateur."),
    }
