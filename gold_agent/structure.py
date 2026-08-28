"""Lecture de structure de marché : pivots, tendance, niveaux clés.

La structure prime sur les indicateurs : un RSI en survente dans une
tendance baissière n'est pas un signal d'achat, c'est une tendance qui
fonctionne.
"""
from __future__ import annotations

from typing import Optional, Sequence


def pivots(highs: Sequence[float], lows: Sequence[float], left: int = 3, right: int = 3):
    """Pivots fractals. `right` bougies de confirmation => les `right`
    dernières bougies ne peuvent pas encore former un pivot confirmé."""
    ph, pl = [], []
    for i in range(left, len(highs) - right):
        window_h = highs[i - left:i + right + 1]
        if highs[i] == max(window_h) and window_h.count(highs[i]) == 1:
            ph.append({"index": i, "price": highs[i]})
        window_l = lows[i - left:i + right + 1]
        if lows[i] == min(window_l) and window_l.count(lows[i]) == 1:
            pl.append({"index": i, "price": lows[i]})
    return {"highs": ph, "lows": pl}


def trend_from_structure(piv: dict, min_points: int = 2) -> dict:
    """Tendance déduite de la séquence des pivots (HH/HL vs LH/LL)."""
    ph = [p["price"] for p in piv["highs"]][-3:]
    pl = [p["price"] for p in piv["lows"]][-3:]
    if len(ph) < min_points or len(pl) < min_points:
        return {"trend": "indetermine", "reason": "pas assez de pivots confirmés"}

    higher_highs = all(ph[i] > ph[i - 1] for i in range(1, len(ph)))
    lower_highs = all(ph[i] < ph[i - 1] for i in range(1, len(ph)))
    higher_lows = all(pl[i] > pl[i - 1] for i in range(1, len(pl)))
    lower_lows = all(pl[i] < pl[i - 1] for i in range(1, len(pl)))

    if higher_highs and higher_lows:
        return {"trend": "haussier", "reason": "sommets et creux ascendants (HH + HL)"}
    if lower_highs and lower_lows:
        return {"trend": "baissier", "reason": "sommets et creux descendants (LH + LL)"}
    if higher_lows and not higher_highs:
        return {"trend": "haussier_affaibli", "reason": "creux ascendants mais sommets plafonnés"}
    if lower_highs and not lower_lows:
        return {"trend": "baissier_affaibli", "reason": "sommets descendants mais creux tenus"}
    return {"trend": "range", "reason": "structure sans direction nette"}


def key_levels(piv: dict, price: float, atr_val: Optional[float], max_levels: int = 3):
    """Supports sous le prix, résistances au-dessus, groupés par proximité."""
    tol = (atr_val * 0.5) if atr_val else (price * 0.002)

    def cluster(points: list[dict]) -> list[dict]:
        prices = sorted(p["price"] for p in points)
        groups: list[list[float]] = []
        for p in prices:
            if groups and abs(p - groups[-1][-1]) <= tol:
                groups[-1].append(p)
            else:
                groups.append([p])
        return [
            {"price": sum(g) / len(g), "touches": len(g)}
            for g in groups
        ]

    highs = cluster(piv["highs"])
    lows = cluster(piv["lows"])
    all_levels = highs + lows

    # Un meme niveau peut sortir a la fois du groupe des sommets et de celui
    # des creux (un ancien support devenu resistance). On fusionne, en
    # cumulant les touches : c'est justement ce qui en fait un niveau fort.
    def fusionner(niveaux: list[dict]) -> list[dict]:
        niveaux = sorted(niveaux, key=lambda l: l["price"])
        fusion: list[dict] = []
        for n in niveaux:
            if fusion and abs(n["price"] - fusion[-1]["price"]) <= tol:
                fusion[-1]["touches"] += n["touches"]
                fusion[-1]["price"] = (fusion[-1]["price"] + n["price"]) / 2
            else:
                fusion.append(dict(n))
        return fusion

    all_levels = fusionner(all_levels)

    resistances = sorted(
        [l for l in all_levels if l["price"] > price], key=lambda l: l["price"]
    )[:max_levels]
    supports = sorted(
        [l for l in all_levels if l["price"] < price], key=lambda l: -l["price"]
    )[:max_levels]

    for lvl in resistances + supports:
        lvl["distance_pct"] = round((lvl["price"] - price) / price * 100, 2)
        lvl["price"] = round(lvl["price"], 2)
    return {"supports": supports, "resistances": resistances}


def swing_range(highs: Sequence[float], lows: Sequence[float], lookback: int = 50):
    window_h = highs[-lookback:]
    window_l = lows[-lookback:]
    hi, lo = max(window_h), min(window_l)
    return {"high": hi, "low": lo, "amplitude": hi - lo, "lookback": len(window_h)}


def rsi_divergence(piv: dict, rsi_series: Sequence[Optional[float]],
                   min_separation: int = 5, min_rsi_gap: float = 2.0) -> list[dict]:
    """Divergences entre le prix et le RSI sur les deux derniers pivots.

    Baissiere : le prix fait un sommet plus haut, le RSI un sommet plus bas
    — la hausse se poursuit avec moins de force derriere elle.
    Haussiere : miroir sur les creux.

    `min_rsi_gap` evite de qualifier de divergence un ecart de RSI
    negligeable, qui n'est que du bruit.
    """
    found: list[dict] = []

    def last_two(points: list[dict]):
        usable = [p for p in points if p["index"] < len(rsi_series)
                  and rsi_series[p["index"]] is not None]
        if len(usable) < 2:
            return None
        a, b = usable[-2], usable[-1]
        if b["index"] - a["index"] < min_separation:
            return None
        return a, b

    pair = last_two(piv["highs"])
    if pair:
        a, b = pair
        ra, rb = rsi_series[a["index"]], rsi_series[b["index"]]
        if b["price"] > a["price"] and rb < ra - min_rsi_gap:
            found.append({
                "type": "baissiere",
                "detail": (f"sommet prix {a['price']:.2f} -> {b['price']:.2f} (plus haut) "
                           f"mais RSI {ra:.1f} -> {rb:.1f} (plus bas)"),
                "force": round(ra - rb, 1),
            })

    pair = last_two(piv["lows"])
    if pair:
        a, b = pair
        ra, rb = rsi_series[a["index"]], rsi_series[b["index"]]
        if b["price"] < a["price"] and rb > ra + min_rsi_gap:
            found.append({
                "type": "haussiere",
                "detail": (f"creux prix {a['price']:.2f} -> {b['price']:.2f} (plus bas) "
                           f"mais RSI {ra:.1f} -> {rb:.1f} (plus haut)"),
                "force": round(rb - ra, 1),
            })

    return found


def momentum_slope(series: Sequence[Optional[float]], lookback: int = 3) -> Optional[str]:
    """Le momentum s'accelere-t-il ou s'essouffle-t-il ?"""
    vals = [v for v in series if v is not None]
    if len(vals) < lookback + 1:
        return None
    recent = vals[-(lookback + 1):]
    diffs = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
    if all(d > 0 for d in diffs):
        return "accelere"
    if all(d < 0 for d in diffs):
        return "s_essouffle"
    return "irregulier"


def fair_value_gaps(opens: Sequence[float], highs: Sequence[float],
                    lows: Sequence[float], closes: Sequence[float],
                    min_size: float = 0.0, lookback: int = 120) -> list[dict]:
    """Fair Value Gaps : déséquilibres à trois bougies.

    FVG haussier : le creux de la bougie i est au-dessus du sommet de i-2.
    Le prix a bondi si vite qu'aucune transaction n'a eu lieu dans
    l'intervalle. FVG baissier : miroir.

    `comble` indique si le prix est depuis revenu dans la zone. Un FVG déjà
    comblé n'a plus de valeur — c'est le non-comblé qui intéresse.
    """
    n = len(closes)
    out: list[dict] = []
    debut = max(2, n - lookback)

    for i in range(debut, n):
        # FVG haussier
        if lows[i] > highs[i - 2]:
            bas, haut = highs[i - 2], lows[i]
            taille = haut - bas
            if taille >= min_size:
                out.append({"type": "haussier", "index": i, "bas": bas, "haut": haut,
                            "taille": taille, "milieu": (bas + haut) / 2})
        # FVG baissier
        elif highs[i] < lows[i - 2]:
            bas, haut = highs[i], lows[i - 2]
            taille = haut - bas
            if taille >= min_size:
                out.append({"type": "baissier", "index": i, "bas": bas, "haut": haut,
                            "taille": taille, "milieu": (bas + haut) / 2})

    # Comblement : le prix est-il revenu dans la zone depuis sa formation ?
    for g in out:
        apres_bas = lows[g["index"] + 1:]
        apres_haut = highs[g["index"] + 1:]
        if not apres_bas:
            g["comble"] = False
            g["comble_pct"] = 0.0
            continue
        if g["type"] == "haussier":
            plus_bas = min(apres_bas)
            penetration = max(0.0, g["haut"] - plus_bas)
        else:
            plus_haut = max(apres_haut)
            penetration = max(0.0, plus_haut - g["bas"])
        g["comble_pct"] = round(min(100.0, penetration / g["taille"] * 100), 1) if g["taille"] else 100.0
        g["comble"] = g["comble_pct"] >= 100.0

    for g in out:
        g["age_bougies"] = n - 1 - g["index"]
        for k in ("bas", "haut", "taille", "milieu"):
            g[k] = round(g[k], 2)

    return out


def fvg_actifs(gaps: list[dict], prix: float, max_retenus: int = 4) -> list[dict]:
    """Les FVG non comblés les plus proches du prix — les seuls exploitables."""
    vivants = [g for g in gaps if not g["comble"]]
    for g in vivants:
        if g["haut"] < prix:
            g["position"] = "sous le prix"
            g["distance"] = round(prix - g["haut"], 2)
        elif g["bas"] > prix:
            g["position"] = "au-dessus du prix"
            g["distance"] = round(g["bas"] - prix, 2)
        else:
            g["position"] = "prix dedans"
            g["distance"] = 0.0
    vivants.sort(key=lambda g: g["distance"])
    return vivants[:max_retenus]
