"""Calculateur de risque — TU fournis l'entrée et le stop, il fait l'arithmétique.

Cet outil ne choisit aucun niveau. Il prend les tiens et calcule ce qui en
découle mécaniquement : taille de position pour un risque donné, et rapport
risque/récompense vers chaque niveau structurel détecté par l'analyse.

Ce n'est pas un conseil : c'est une calculatrice.
"""
from __future__ import annotations

import json
from pathlib import Path

DERNIER = Path.home() / ".gold_agent_last.json"

# 1 lot standard XAUUSD = 100 onces, donc 1 point de mouvement = 100 $ par lot.
VALEUR_POINT_PAR_LOT = 100.0


def charger_niveaux() -> tuple[list[dict], dict]:
    """Récupère les niveaux du dernier rapport d'analyse."""
    if not DERNIER.exists():
        raise FileNotFoundError(
            "Aucune analyse en mémoire. Lance d'abord : python3 -m gold_agent --m1")
    rep = json.loads(DERNIER.read_text())

    niveaux: list[dict] = []
    for tf in rep.get("timeframes", []):
        lab = tf["timeframe"]
        for r in tf.get("levels", {}).get("resistances", []):
            niveaux.append({"prix": r["price"], "type": "résistance", "tf": lab,
                            "touches": r.get("touches", 0)})
        for sp in tf.get("levels", {}).get("supports", []):
            niveaux.append({"prix": sp["price"], "type": "support", "tf": lab,
                            "touches": sp.get("touches", 0)})
        for g in tf.get("fvg", []):
            niveaux.append({"prix": g["milieu"], "type": f"FVG {g['type']}", "tf": lab,
                            "touches": 0})
        mo = tf.get("motifs") or {}
        for ob in mo.get("order_blocks", []):
            niveaux.append({"prix": ob["milieu"], "type": f"OB {ob['type']} ({ob['etat']})",
                            "tf": lab, "touches": 0})
        for ss in mo.get("sessions", [])[-3:]:
            niveaux.append({"prix": ss["haut"], "type": f"haut {ss['session']}", "tf": lab, "touches": 0})
            niveaux.append({"prix": ss["bas"], "type": f"bas {ss['session']}", "tf": lab, "touches": 0})

    inv = (rep.get("synthese") or {}).get("invalidation")
    if inv:
        niveaux.append({"prix": inv["niveau"], "type": "INVALIDATION", "tf": "H4", "touches": 0})

    # Dédoublonnage
    vus, uniques = set(), []
    for n in sorted(niveaux, key=lambda x: x["prix"]):
        cle = round(n["prix"], 1)
        if cle in vus:
            continue
        vus.add(cle)
        uniques.append(n)
    return uniques, rep


def calculer(entree: float, stop: float, capital: float, risque_pct: float = 1.0,
             tp: float | None = None) -> dict:
    """Arithmétique de position. Aucune recommandation."""
    if entree == stop:
        raise ValueError("L'entrée et le stop ne peuvent pas être au même prix.")

    sens = "achat" if stop < entree else "vente"
    distance = abs(entree - stop)
    risque_eur = capital * risque_pct / 100.0
    lots = risque_eur / (distance * VALEUR_POINT_PAR_LOT)

    niveaux, rep = charger_niveaux()

    # Niveaux situés dans le sens du trade, au-delà de l'entrée
    cibles = []
    for n in niveaux:
        gain = (n["prix"] - entree) if sens == "achat" else (entree - n["prix"])
        if gain <= 0:
            continue
        cibles.append({**n, "gain_pts": round(gain, 2),
                       "rr": round(gain / distance, 2),
                       "gain_eur": round(gain * VALEUR_POINT_PAR_LOT * lots, 2)})
    cibles.sort(key=lambda x: x["gain_pts"])

    # Contexte de volatilité
    atrs = {t["timeframe"]: t["indicators"].get("atr14") for t in rep.get("timeframes", [])}
    stop_en_atr = {k: round(distance / v, 2) for k, v in atrs.items() if v}

    resultat = {
        "sens": sens,
        "entree": entree, "stop": stop,
        "distance_pts": round(distance, 2),
        "capital": capital, "risque_pct": risque_pct,
        "risque_montant": round(risque_eur, 2),
        "taille_lots": round(lots, 4),
        "taille_onces": round(lots * 100, 1),
        "valeur_point": round(lots * VALEUR_POINT_PAR_LOT, 2),
        "stop_en_atr": stop_en_atr,
        "cibles_structurelles": cibles,
        "garde_fou": (rep.get("garde_fou") or {}).get("decision"),
        "analyse_du": rep.get("generated_at"),
    }

    if tp is not None:
        gain = (tp - entree) if sens == "achat" else (entree - tp)
        resultat["tp_fourni"] = {
            "prix": tp, "gain_pts": round(gain, 2),
            "rr": round(gain / distance, 2) if distance else None,
            "gain_eur": round(gain * VALEUR_POINT_PAR_LOT * lots, 2),
            "coherent": gain > 0,
        }
    return resultat


def rendre(r: dict) -> str:
    L = []
    a = L.append
    a("=" * 66)
    a(f"  CALCUL DE POSITION — {r['sens'].upper()}")
    a(f"  Analyse de reference : {r['analyse_du']}")
    a("=" * 66)
    a("")
    a(f"  Entree {r['entree']}   Stop {r['stop']}   Distance {r['distance_pts']} pts")
    if r["stop_en_atr"]:
        a("  Stop en ATR : " + "  ".join(f"{k} {v}x" for k, v in r["stop_en_atr"].items()))
    a("")
    a(f"  Capital {r['capital']:,.0f}   Risque {r['risque_pct']}% = {r['risque_montant']:,.2f}")
    a(f"  -> Taille : {r['taille_lots']} lot ({r['taille_onces']} onces)")
    a(f"  -> Chaque point vaut {r['valeur_point']:.2f}")
    if r.get("tp_fourni"):
        t = r["tp_fourni"]
        if not t["coherent"]:
            a(f"\n  ATTENTION : le TP {t['prix']} est du mauvais cote de l'entree pour un {r['sens']}.")
        else:
            a(f"\n  TP fourni {t['prix']} : +{t['gain_pts']} pts, R:R {t['rr']}, gain {t['gain_eur']:,.2f}")
    a("")
    a("  NIVEAUX STRUCTURELS DANS LE SENS DU TRADE")
    a("  (detectes par l'analyse — a toi de choisir lesquels retenir)")
    a("")
    if not r["cibles_structurelles"]:
        a("    aucun niveau detecte au-dela de l'entree dans ce sens")
    for c in r["cibles_structurelles"][:12]:
        a(f"    {c['prix']:>9.2f}  {c['type']:<26} {c['tf']:<3} "
          f"+{c['gain_pts']:>7.2f} pts  R:R {c['rr']:>5.2f}  {c['gain_eur']:>10,.2f}")
    a("")
    if r.get("garde_fou"):
        a(f"  Rappel — verdict du garde-fou sur la derniere analyse : {r['garde_fou']}")
    a("")
    a("  Calculatrice, pas recommandation. Les niveaux d'entree et de stop")
    a("  sont ceux que TU as fournis. Aucun ordre n'est passe.")
    a("=" * 66)
    return "\n".join(L)
