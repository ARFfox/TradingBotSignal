"""Rendu lisible du rapport d'analyse."""
from __future__ import annotations

BIAS_LABEL = {
    "haussier": "HAUSSIER", "haussier_faible": "haussier faible", "neutre": "NEUTRE",
    "baissier_faible": "baissier faible", "baissier": "BAISSIER",
}


def render(rep: dict) -> str:
    L: list[str] = []
    add = L.append

    add("=" * 68)
    add(f"  ANALYSE OR — {rep['symbol']}")
    add(f"  {rep['generated_at']}")
    add("=" * 68)

    # Le verdict du garde-fou passe en premier : c'est la conclusion utile.
    gate = rep.get("garde_fou")
    if gate:
        add("")
        add(f"VERDICT : {gate['decision']}")
        add(f"  {gate['motif']}")
        add(f"  Poids des arguments — haussier {gate['poids_haussier']} / "
            f"baissier {gate['poids_baissier']}  ({gate['part_haussiere_pct']:.0f}% haussier)")
        for v in gate["vetos"]:
            add(f"  VETO : {v}")
        for r in gate["reserves"]:
            add(f"  Reserve : {r}")

    syn = rep["synthese"]
    add("")
    add(f"SYNTHESE : {syn['verdict']}")
    add(f"  {syn['detail']}")
    if syn.get("invalidation"):
        inv = syn["invalidation"]
        add(f"  Invalidation : {inv['niveau']} — {inv['sens']}")
    if syn.get("alertes_extension"):
        add("")
        add("  ALERTES D'EXTENSION :")
        for a in syn["alertes_extension"]:
            add(f"    ! {a}")

    for tf in rep["timeframes"]:
        i = tf["indicators"]
        add("")
        add("-" * 68)
        add(f"{tf['timeframe']} ({tf['role']})   prix {tf['price']}   "
            f"biais {BIAS_LABEL.get(tf['bias'], tf['bias'])} (score {tf['score']:+d})")
        add(f"  Structure : {tf['trend_structure']['trend']} — {tf['trend_structure']['reason']}")
        add(f"  Force     : {tf['force']}"
            + (f" (ADX {i['adx14']})" if i["adx14"] is not None else ""))
        pf, ps = tf.get("ema_periods", [50, 200])
        add(f"  EMA{pf} {i['ema_fast']}   EMA{ps} {i['ema_slow']}   RSI {i['rsi14']}   ATR {i['atr14']}")
        for d in tf.get("divergences", []):
            add(f"  Divergence {d['type']} : {d['detail']}")
        mo = tf.get("motifs") or {}
        if mo:
            el = mo.get("elliott") or {}
            if el.get("comptage"):
                rr = el["ratios"]
                add(f"  ELLIOTT : impulsion {el['direction']}")
                for v in el["vagues"]:
                    enc = " (en cours)" if v["en_cours"] else ""
                    add(f"    V{v['num']}  {v['de']:>9.2f} -> {v['vers']:>9.2f}   "
                        f"{v['amplitude']:>7.2f} pts{enc}")
                add(f"    V2 retrace {rr['w2_retrace_w1']:.0%} de V1 | "
                    f"V3 = {rr['w3_extension_w1']:.2f}x V1 | V4 retrace {rr['w4_retrace_w3']:.0%} de V3")
            else:
                add(f"  ELLIOTT : aucun comptage valide — {el.get('raison','')}")
                for v in el.get("violations", []):
                    add(f"    {v}")
            jbs = mo.get("jambes") or []
            if jbs:
                add("  Jambes recentes (zigzag) :")
                for j in jbs[-4:]:
                    enc = " (en cours)" if j["en_cours"] else ""
                    add(f"    {j['sens']:<7} {j['de']:>9.2f} -> {j['vers']:>9.2f}  "
                        f"{j['amplitude']:>7.2f} pts / {j['bougies']} bougies{enc}")
            obs = mo.get("order_blocks") or []
            add(f"  Order blocks : {mo.get('order_blocks_total',0)} detectes, "
                f"{mo.get('order_blocks_casses',0)} casses, {len(obs)} exploitables")
            for ob in obs:
                add(f"    {ob['type']:<9} {ob['bas']}-{ob['haut']}  impulsion {ob['impulsion_atr']} ATR  "
                    f"[{ob['etat']}]  il y a {ob['age_bougies']} bougies")
            ss = mo.get("sessions") or []
            if ss:
                add("  Sessions (UTC) :")
                for x in ss[-6:]:
                    add(f"    {x['jour']} {x['session']:<9} {x['bas']:>9.2f}-{x['haut']:<9.2f} "
                        f"amplitude {x['amplitude']:>6.2f}")
        if tf.get("fvg"):
            add("  FVG non combles (les plus proches) :")
            for g in tf["fvg"]:
                add(f"    {g['type']:<9} {g['bas']}-{g['haut']}  milieu {g['milieu']}  "
                    f"{g['position']}, a {g['distance']} pts  (taille {g['taille']})")
        add("  Signaux :")
        for s in tf["signals"]:
            add(f"    - {s}")
        lv = tf["levels"]
        if lv["resistances"]:
            add("  Resistances : " + ", ".join(
                f"{r['price']} ({r['distance_pct']:+.2f}%, {r['touches']}x)" for r in lv["resistances"]))
        if lv["supports"]:
            add("  Supports    : " + ", ".join(
                f"{s['price']} ({s['distance_pct']:+.2f}%, {s['touches']}x)" for s in lv["supports"]))

    dbt = rep.get("debat")
    if dbt:
        add("")
        add("=" * 68)
        add("DEBAT CONTRADICTOIRE")
        add("  Les deux theses sont construites separement a partir des memes")
        add("  donnees, pour que les contre-arguments restent visibles.")
        for camp, titre in (("haussier", "THESE HAUSSIERE"), ("baissier", "THESE BAISSIERE")):
            args = dbt.get(camp, [])
            somme = sum(a["poids"] for a in args)
            add("")
            add(f"  {titre}  (poids total {somme:.1f})")
            if not args:
                add("    aucun argument")
            for a in args:
                add(f"    [{a['poids']:>4.1f}] {a['timeframe']:<5} {a['argument']}")

    if rep.get("contexte_macro"):
        add("")
        add("-" * 68)
        add("CONTEXTE MACRO (correlation inverse a l'or)")
        for sym, d in rep["contexte_macro"].items():
            var = f"{d['variation_5j_pct']:+.2f}%" if d.get("variation_5j_pct") is not None else "n/a"
            add(f"  {sym:<12} {d['close']}  {d.get('position') or ''}  5j: {var}")

    if rep.get("erreurs"):
        add("")
        add("AVERTISSEMENTS :")
        for e in rep["erreurs"]:
            add(f"  ! {e}")

    add("")
    add("-" * 68)
    add(rep["avertissement"])
    add("=" * 68)
    return "\n".join(L)
