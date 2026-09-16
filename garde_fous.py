#!/usr/bin/env python3
"""
GARDE-FOUS — les trois correctifs qui valent plus que tout le reste.

    python3 garde_fous.py        # démonstration

Diagnostic au 16/09/2026 : 548 signaux émis, 288 résolus, −77,98R.
Trois pannes expliquent l'essentiel, et aucune ne demande d'intelligence :

  1. STOPS DANS LE BRUIT    cuivre M5, entrée 6.50 / SL 6.49 — 2 à 5 fois
                            le spread. Le prix le touche en respirant.
  2. SIGNAUX CONTRADICTOIRES GDX en achat ET en vente à 12:17. L'un des
                            deux perd forcément.
  3. AUCUN SUIVI DES SL     on sait qu'un stop a sauté, jamais POURQUOI.
                            Sans ça, le superviseur n'a rien à apprendre.

Ce module corrige les trois. Le troisième est le plus important : c'est
lui qui produit les données dont `superviseur_apprenant` a besoin. Sans
lui, tout le reste est affamé.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
SL_MIN_ATR = 1.0          # sous 1 ATR, un stop est du bruit, pas une invalidation
MARGE_SPREAD = 2.0        # le stop doit aussi dépasser 2 spreads
RR_MIN = 1.5              # après élargissement du stop, le R:R doit tenir
HORIZON_DEFAUT = 48       # bougies de vie d'un signal


# ==========================================================================
# 1. LE STOP MINIMUM
# ==========================================================================
@dataclass
class Stop:
    valeur: float
    distance_atr: float
    ajuste: bool
    motif: str


def stop_minimum(entree: float, sl_propose: float, sens: str,
                 atr: float, spread: float = 0.0) -> Stop:
    """Élargit un stop trop serré, sans jamais le resserrer.

    Deux contraintes, on garde la plus large :
      · au moins SL_MIN_ATR × ATR  — au-delà du bruit du timeframe
      · au moins MARGE_SPREAD × spread — au-delà du coût d'entrée

    Le stop n'est JAMAIS resserré, même si l'analyse le proposait plus
    loin : un stop structurel plus large que le minimum est un stop
    structurel, et c'est lui qui a raison.
    """
    if atr <= 0:
        return Stop(sl_propose, 0.0, False, "ATR inconnu — stop laissé tel quel")

    distance = abs(entree - sl_propose)
    minimum = max(SL_MIN_ATR * atr, MARGE_SPREAD * spread)

    if distance >= minimum:
        return Stop(sl_propose, distance / atr, False, "stop conforme")

    signe = -1 if sens == "achat" else 1
    neuf = entree + signe * minimum
    return Stop(neuf, minimum / atr, True,
                f"stop élargi de {distance / atr:.2f} à {minimum / atr:.2f} ATR")


def valider_signal(entree: float, sl: float, tp: float, sens: str,
                   atr: float, spread: float = 0.0) -> dict:
    """Contrôle complet avant émission. Retourne le signal corrigé ou un refus.

    L'ordre compte : on élargit le stop D'ABORD, puis on vérifie le R:R.
    Élargir un stop dégrade le R:R — un setup qui n'y survit pas n'aurait
    jamais dû être émis, il tenait uniquement grâce à un stop irréaliste.
    """
    s = stop_minimum(entree, sl, sens, atr, spread)
    risque = abs(entree - s.valeur)
    if risque <= 0:
        return {"ok": False, "motif": "risque nul — entrée et stop confondus"}

    rr = abs(tp - entree) / risque
    if rr < RR_MIN:
        return {"ok": False, "sl": s.valeur, "rr": round(rr, 2),
                "motif": (f"R:R {rr:.2f} sous {RR_MIN} après élargissement du "
                          f"stop — le setup ne tenait que par un stop irréaliste")}

    return {"ok": True, "sl": s.valeur, "rr": round(rr, 2),
            "sl_en_atr": round(s.distance_atr, 2),
            "stop_ajuste": s.ajuste, "motif": s.motif}


# ==========================================================================
# 2. ANTI-CONTRADICTION ET ANTI-DOUBLON
# ==========================================================================
def filtrer_lot(candidats: list[dict], fenetre_doublon_s: int = 1800) -> tuple:
    """Un instrument ne peut pas être acheté et vendu en même temps.

    Les candidats sont traités du meilleur au moins bon : en cas de
    contradiction, c'est le signal le plus fort qui survit.
    """
    gardes, refuses = [], []
    for c in sorted(candidats, key=lambda x: -x.get("note", 0)):
        contra = next((g for g in gardes
                       if g["instrument"] == c["instrument"]
                       and g["sens"] != c["sens"]), None)
        if contra:
            refuses.append({**c, "motif": f"contredit {contra['tf']} "
                                          f"({contra['sens']} vs {c['sens']})"})
            continue
        doublon = next((g for g in gardes
                        if g["instrument"] == c["instrument"]
                        and g["sens"] == c["sens"]
                        and abs(g["cree_ts"] - c["cree_ts"]) < fenetre_doublon_s), None)
        if doublon:
            refuses.append({**c, "motif": f"doublon de {doublon['tf']}"})
            continue
        gardes.append(c)
    return gardes, refuses


# ==========================================================================
# 3. LE SUIVI — la pièce qui alimente l'apprentissage
# ==========================================================================
@dataclass
class Resolution:
    statut: str                      # en_attente | TP | SL | expire
    entree_touchee: bool = False
    extreme_favorable: float | None = None   # meilleur prix atteint après entrée
    tp_atteint_apres_sl: bool = False
    bougies_jusqu_a_entree: int | None = None
    bougies_jusqu_a_sortie: int | None = None
    r_realise: float | None = None


def suivre(signal: dict, bougies: list[dict],
           horizon: int = HORIZON_DEFAUT) -> Resolution:
    """Rejoue un signal contre les bougies qui ont suivi son émission.

    `bougies` : [{"high": float, "low": float, "close": float}, ...] dans
    l'ordre chronologique, à partir de l'émission.

    DEUX CHOIX DE MÉTHODE, tous les deux pessimistes et assumés :

    1. Quand une bougie touche le SL ET le TP, on suppose le SL EN PREMIER.
       En OHLC on ne connaît pas l'ordre des extrêmes dans la bougie.
       Supposer le TP gonflerait artificiellement les résultats — et un
       backtest optimiste est pire qu'un backtest absent, parce qu'on lui
       fait confiance.

    2. Après un SL, on CONTINUE de scanner jusqu'à l'horizon pour savoir si
       le TP aurait été atteint. C'est ce qui distingue « stop trop serré »
       de « direction fausse », et c'est la seule information qui permet au
       superviseur de corriger la bonne chose.
    """
    e, sl, tp = signal["entree"], signal["sl"], signal["tp"]
    achat = signal["sens"] == "achat"
    risque = abs(e - sl)
    r = Resolution(statut="en_attente")
    if risque <= 0 or not bougies:
        return r

    entree_i = None
    for i, b in enumerate(bougies[:horizon]):
        haut, bas = b["high"], b["low"]

        # --- l'entrée limite est-elle touchée ? -------------------------
        if entree_i is None:
            if (achat and bas <= e) or (not achat and haut >= e):
                entree_i = i
                r.entree_touchee = True
                r.bougies_jusqu_a_entree = i
                r.extreme_favorable = e
            else:
                continue

        # --- suivi de l'extrême favorable -------------------------------
        favorable = haut if achat else bas
        if r.extreme_favorable is None:
            r.extreme_favorable = favorable
        elif (achat and favorable > r.extreme_favorable) or \
             (not achat and favorable < r.extreme_favorable):
            r.extreme_favorable = favorable

        # --- résolution --------------------------------------------------
        if r.statut in ("en_attente",):
            touche_sl = bas <= sl if achat else haut >= sl
            touche_tp = haut >= tp if achat else bas <= tp
            if touche_sl:                       # pessimiste : SL d'abord
                r.statut = "SL"
                r.r_realise = -1.0
                r.bougies_jusqu_a_sortie = i
            elif touche_tp:
                r.statut = "TP"
                r.r_realise = abs(tp - e) / risque
                r.bougies_jusqu_a_sortie = i
                return r
        else:
            # après un SL : le TP aurait-il été atteint ?
            if (achat and haut >= tp) or (not achat and bas <= tp):
                r.tp_atteint_apres_sl = True
                return r

    if entree_i is None:
        r.statut = "expire"      # jamais entré : ne compte dans aucun taux
    return r


def champs_journal() -> dict:
    """Les champs que `journal.py` DOIT enregistrer.

    Sans `atr`, aucun stop ne peut être jugé.
    Sans `tp_atteint_apres_sl`, les deux causes de SL sont indiscernables.
    Sans `emis`, le taux de réussite mélange ce qui a été affiché et ce
    qui a été rejeté — et ne veut plus rien dire.
    """
    return {
        "emis": "bool — ce signal t'a-t-il été AFFICHÉ ou NOTIFIÉ ?",
        "atr": "float — ATR du timeframe AU MOMENT de l'émission",
        "spread": "float — spread constaté à l'émission",
        "extreme_favorable": "float — meilleur prix atteint après l'entrée",
        "tp_atteint_apres_sl": "bool — le TP a-t-il été touché après le stop ?",
        "bougies_jusqu_a_entree": "int|null",
        "bougies_jusqu_a_sortie": "int|null",
        "r_realise": "float|null",
        "intermarche": "dict — score, base, fiable (voir AG-10 Miroir)",
    }


# ==========================================================================
if __name__ == "__main__":
    L = "=" * 70
    print(f"{L}\n  GARDE-FOUS — démonstration sur les cas réels du journal\n{L}\n")

    print("  1. LE STOP MINIMUM\n")
    for nom, e, sl, atr, sp in [
            ("CUIVRE M5  (cas réel)", 6.50, 6.49, 0.035, 0.003),
            ("XAU/USD M5 (cas réel)", 4331.82, 4328.10, 4.20, 0.30),
            ("XAU/USD H1 (stop sain)", 4331.82, 4310.00, 12.0, 0.30)]:
        s = stop_minimum(e, sl, "achat", atr, sp)
        etat = "ÉLARGI  " if s.ajuste else "conforme"
        print(f"    {nom:<24} {etat} {sl:g} → {s.valeur:.4g}   {s.motif}")

    print("\n  2. VALIDATION COMPLÈTE\n")
    v = valider_signal(6.50, 6.49, 6.53, "achat", 0.035, 0.003)
    print(f"    CUIVRE M5 : {'ACCEPTÉ' if v['ok'] else 'REFUSÉ'} — {v['motif']}")

    print("\n  3. ANTI-CONTRADICTION\n")
    lot = [{"instrument": "GDX", "tf": "M15", "sens": "vente",
            "note": 0.27, "cree_ts": 1000},
           {"instrument": "GDX", "tf": "M5", "sens": "achat",
            "note": 0.43, "cree_ts": 1000}]
    g, ref = filtrer_lot(lot)
    print(f"    gardés : {[x['tf'] + ' ' + x['sens'] for x in g]}")
    for x in ref:
        print(f"    refusé : {x['tf']} {x['sens']} — {x['motif']}")

    print("\n  4. SUIVI — les deux causes d'un stop touché\n")
    sig = {"entree": 100.0, "sl": 98.0, "tp": 106.0, "sens": "achat"}
    cas = {
        "stop trop serré (TP après le SL)":
            [{"high": 100.5, "low": 99.0, "close": 100.0},
             {"high": 101.0, "low": 97.5, "close": 98.0},
             {"high": 107.0, "low": 99.0, "close": 106.5}],
        "direction fausse (jamais parti)":
            [{"high": 100.2, "low": 99.5, "close": 99.8},
             {"high": 100.1, "low": 97.0, "close": 97.5},
             {"high": 97.8, "low": 95.0, "close": 95.5}],
        "objectif atteint":
            [{"high": 100.5, "low": 99.2, "close": 100.1},
             {"high": 106.5, "low": 100.0, "close": 106.2}],
        "jamais entré":
            [{"high": 105.0, "low": 101.0, "close": 104.0}],
    }
    for nom, bougies in cas.items():
        r = suivre(sig, bougies)
        sup = "  → TP atteint APRÈS le stop" if r.tp_atteint_apres_sl else ""
        print(f"    {nom:<34} {r.statut:<10} R={r.r_realise}{sup}")
    print()
