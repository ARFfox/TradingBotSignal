"""Rendus SVG des graphiques : chandeliers des cartes et grand
graphique annote (EMA, S/R, zigzag, ABC, Fibonacci).
"""
from __future__ import annotations

from . import indicators as _ind, patterns as _pat, structure as _st

def _chandeliers(bougies: list, setup: dict, largeur=560, hauteur=200) -> str:
    """Graphique en chandeliers SVG, avec les zones du setup superposées."""
    if not bougies:
        return ""
    marge_d, marge_h = 52, 8
    zone_l = largeur - marge_d
    zone_h = hauteur - marge_h * 2

    prix = [b["h"] for b in bougies] + [b["l"] for b in bougies]
    for cle in ("entree", "stop", "objectif"):
        v = (setup or {}).get(cle)
        if v:
            prix.append(v)
    pmin, pmax = min(prix), max(prix)
    if pmax == pmin:
        pmax = pmin + 1
    marge_p = (pmax - pmin) * 0.06
    pmin, pmax = pmin - marge_p, pmax + marge_p

    def y(p):
        return marge_h + (pmax - p) / (pmax - pmin) * zone_h

    pas = zone_l / max(len(bougies), 1)
    corps = max(1.4, pas * 0.6)
    out = [f'<svg viewBox="0 0 {largeur} {hauteur}" width="100%" height="{hauteur}" '
           f'xmlns="http://www.w3.org/2000/svg">']

    # Zones du setup
    for cle, couleur in (("entree", "#2f81f7"), ("stop", "#f85149"), ("objectif", "#3fb950")):
        z = (setup or {}).get(f"{cle}_zone")
        if not z:
            continue
        y1, y2 = y(z[1]), y(z[0])
        out.append(f'<rect x="0" y="{y1:.1f}" width="{zone_l:.1f}" height="{max(abs(y2-y1),1.5):.1f}" '
                   f'fill="{couleur}" fill-opacity="0.16"/>')
        out.append(f'<line x1="0" y1="{y(( z[0]+z[1])/2):.1f}" x2="{zone_l:.1f}" '
                   f'y2="{y((z[0]+z[1])/2):.1f}" stroke="{couleur}" stroke-width="1.2" stroke-dasharray="4 3"/>')

    # Chandeliers
    for i, b in enumerate(bougies):
        x = i * pas + pas / 2
        hausse = b["c"] >= b["o"]
        col = "#3fb950" if hausse else "#f85149"
        out.append(f'<line x1="{x:.1f}" y1="{y(b["h"]):.1f}" x2="{x:.1f}" y2="{y(b["l"]):.1f}" '
                   f'stroke="{col}" stroke-width="1"/>')
        yo, yc = y(b["o"]), y(b["c"])
        out.append(f'<rect x="{x - corps/2:.1f}" y="{min(yo,yc):.1f}" width="{corps:.1f}" '
                   f'height="{max(abs(yc-yo),1):.1f}" fill="{col}"/>')

    # Echelle de prix
    for frac in (0, 0.5, 1):
        p = pmin + (pmax - pmin) * frac
        yy = y(p)
        out.append(f'<line x1="0" y1="{yy:.1f}" x2="{zone_l:.1f}" y2="{yy:.1f}" '
                   f'stroke="#30363d" stroke-width="0.5"/>')
        out.append(f'<text x="{zone_l + 6}" y="{yy + 3.5:.1f}" fill="#8b949e" '
                   f'font-size="10.5" font-family="monospace">{p:.0f}</text>')
    out.append("</svg>")
    return "".join(out)


def _grand_graphique(r: dict, largeur=920, hauteur=380) -> str:
    """Grand graphique AVEC l'analyse dessinée : EMA, supports/résistances,
    zigzag, scénario ABC, équilibre du range — présents même sans signal.

    Tout est recalculé depuis les 120 bougies de la carte : aucune requête
    supplémentaire, et le dessin reste fidèle à ce que les modules voient.
    """
    bougies = r.get("bougies") or []
    if len(bougies) < 30:
        return _chandeliers(bougies, r.get("setup") or {}, largeur, hauteur)

    o = [b["o"] for b in bougies]; hh = [b["h"] for b in bougies]
    ll = [b["l"] for b in bougies]; cc = [b["c"] for b in bougies]
    atr = r.get("atr") or 1.0
    setup = r.get("setup") or {}

    pf, ps = 20, 50
    ema_f = _ind.ema(cc, pf); ema_s = _ind.ema(cc, ps)
    piv = _st.pivots(hh, ll, left=3, right=3)
    niveaux = _st.key_levels(piv, cc[-1], atr, max_levels=3)
    zz = _pat.zigzag(hh, ll, seuil=atr * 2)
    abc = r.get("abc") or {}
    pd_ = (r.get("ict") or {}).get("premium_discount") or {}

    marge_d, marge_h = 56, 10
    zone_l = largeur - marge_d
    zone_h = hauteur - marge_h * 2
    prix_tous = hh + ll
    for src in (setup.get("entree"), setup.get("stop"), setup.get("objectif"),
                abc.get("cible_C")):
        if src: prix_tous.append(src)
    pmin, pmax = min(prix_tous), max(prix_tous)
    mp = (pmax - pmin) * 0.05 or 1
    pmin, pmax = pmin - mp, pmax + mp

    def y(pv): return marge_h + (pmax - pv) / (pmax - pmin) * zone_h
    pas = zone_l / len(bougies)
    corps = max(1.6, pas * 0.62)
    out = [f'<svg viewBox="0 0 {largeur} {hauteur}" width="100%" height="{hauteur}" '
           f'xmlns="http://www.w3.org/2000/svg" style="font-family:-apple-system,sans-serif">']

    # Grille + echelle
    for frac in (0, 0.25, 0.5, 0.75, 1):
        pv = pmin + (pmax - pmin) * frac; yy = y(pv)
        out.append(f'<line x1="0" y1="{yy:.1f}" x2="{zone_l:.1f}" y2="{yy:.1f}" stroke="#21262d" stroke-width="0.6"/>')
        out.append(f'<text x="{zone_l+6}" y="{yy+3.5:.1f}" fill="#8b949e" font-size="10.5" font-family="monospace">{pv:.0f}</text>')

    # Equilibre premium/discount
    if pd_.get("equilibre"):
        ye = y(pd_["equilibre"])
        out.append(f'<line x1="0" y1="{ye:.1f}" x2="{zone_l:.1f}" y2="{ye:.1f}" stroke="#8b949e" stroke-width="1" stroke-dasharray="2 5"/>')
        out.append(f'<text x="4" y="{ye-4:.1f}" fill="#8b949e" font-size="10">équilibre {pd_["equilibre"]:.0f} · {pd_.get("zone","")}</text>')

    # Supports / resistances (pivots agreges)
    for lst, coul, lib in ((niveaux.get("supports", []), "#3fb950", "S"),
                           (niveaux.get("resistances", []), "#f85149", "R")):
        for nv in lst:
            yy = y(nv["price"])
            if not (marge_h <= yy <= hauteur - marge_h): continue
            out.append(f'<line x1="0" y1="{yy:.1f}" x2="{zone_l:.1f}" y2="{yy:.1f}" stroke="{coul}" stroke-width="1" stroke-dasharray="6 4" stroke-opacity="0.55"/>')
            out.append(f'<text x="4" y="{yy-3:.1f}" fill="{coul}" font-size="10">{lib} {nv["price"]:.1f} ({nv["touches"]}x)</text>')

    # Scenario ABC : zone cible + invalidation
    if abc.get("scenario"):
        zc = abc["zone_C"]; y1, y2 = y(zc[1]), y(zc[0])
        if y1 < hauteur and y2 > 0:
            out.append(f'<rect x="0" y="{max(y1,0):.1f}" width="{zone_l:.1f}" height="{max(abs(y2-y1),2):.1f}" fill="#a371f7" fill-opacity="0.14"/>')
            out.append(f'<text x="4" y="{max(y1,10)+12:.1f}" fill="#a371f7" font-size="10.5">cible C {abc["cible_C"]:.0f} — {abc["stade"]}</text>')
        yi = y(abc["invalidation"])
        if 0 < yi < hauteur:
            out.append(f'<line x1="0" y1="{yi:.1f}" x2="{zone_l:.1f}" y2="{yi:.1f}" stroke="#a371f7" stroke-width="1" stroke-dasharray="3 3"/>')
            out.append(f'<text x="4" y="{yi-3:.1f}" fill="#a371f7" font-size="10">invalidation ABC {abc["invalidation"]:.0f}</text>')

    # Zones du setup si present
    for cle, coul in (("entree_zone", "#2f81f7"), ("stop_zone", "#f85149"), ("objectif_zone", "#3fb950")):
        z = setup.get(cle)
        if not z: continue
        y1, y2 = y(z[1]), y(z[0])
        out.append(f'<rect x="0" y="{y1:.1f}" width="{zone_l:.1f}" height="{max(abs(y2-y1),1.5):.1f}" fill="{coul}" fill-opacity="0.15"/>')

    # Fibonacci du Traceur : retracements de la DERNIERE jambe du zigzag.
    # 38,2 / 50 / 61,8 — niveaux de reference, pas des promesses.
    if len(zz) >= 2:
        a_, b_ = zz[-2]["prix"], zz[-1]["prix"]
        for ratio in (0.382, 0.5, 0.618):
            niv = b_ - (b_ - a_) * ratio
            yy = y(niv)
            if marge_h <= yy <= hauteur - marge_h:
                out.append(f'<line x1="0" y1="{yy:.1f}" x2="{zone_l:.1f}" y2="{yy:.1f}" '
                           f'stroke="#e3b341" stroke-width="0.8" stroke-dasharray="2 6" stroke-opacity="0.7"/>')
                out.append(f'<text x="{zone_l-64}" y="{yy-3:.1f}" fill="#e3b341" '
                           f'font-size="9.5">fib {ratio*100:.1f} · {niv:.1f}</text>')

    # Zigzag
    pts = " ".join(f"{p_['index']*pas+pas/2:.1f},{y(p_['prix']):.1f}" for p_ in zz)
    if pts:
        out.append(f'<polyline points="{pts}" fill="none" stroke="#ffa726" stroke-width="1.4" stroke-opacity="0.75"/>')

    # Chandeliers
    for i, b in enumerate(bougies):
        x = i * pas + pas / 2
        coul = "#3fb950" if b["c"] >= b["o"] else "#f85149"
        out.append(f'<line x1="{x:.1f}" y1="{y(b["h"]):.1f}" x2="{x:.1f}" y2="{y(b["l"]):.1f}" stroke="{coul}" stroke-width="1"/>')
        yo, yc = y(b["o"]), y(b["c"])
        out.append(f'<rect x="{x-corps/2:.1f}" y="{min(yo,yc):.1f}" width="{corps:.1f}" height="{max(abs(yc-yo),1):.1f}" fill="{coul}"/>')

    # EMA par-dessus les bougies
    for serie, coul, lib in ((ema_f, "#58a6ff", f"EMA{pf}"), (ema_s, "#f0883e", f"EMA{ps}")):
        pts = " ".join(f"{i*pas+pas/2:.1f},{y(v):.1f}" for i, v in enumerate(serie) if v is not None)
        if pts:
            out.append(f'<polyline points="{pts}" fill="none" stroke="{coul}" stroke-width="1.5" stroke-opacity="0.9"/>')

    # Legende
    out.append(f'<text x="4" y="{hauteur-6}" fill="#6e7681" font-size="10">'
               f'<tspan fill="#58a6ff">— EMA{pf}</tspan>  <tspan fill="#f0883e">— EMA{ps}</tspan>  '
               f'<tspan fill="#ffa726">— zigzag</tspan>  <tspan fill="#3fb950">-- support</tspan>  '
               f'<tspan fill="#f85149">-- résistance</tspan>  <tspan fill="#a371f7">▮ scénario ABC</tspan>  <tspan fill="#e3b341">·· Fibonacci</tspan></text>')
    out.append("</svg>")
    return "".join(out)


