#!/usr/bin/env python3
"""
AG-00 SUPERVISEUR APPRENANT — il se recalibre sur ses propres résultats.

    python3 superviseur_apprenant.py            # démonstration
    python3 superviseur_apprenant.py journal.json

Ce que ce module fait, et ce qu'il ne fait pas
----------------------------------------------
IL FAIT :
  · classer chaque SL en "stop trop serré" ou "direction fausse" —
    ce sont deux pannes opposées, et les confondre empêche toute correction
  · mesurer si la note de confiance est CALIBRÉE (un signal noté 40 %
    gagne-t-il 40 % du temps ?)
  · mesurer le poids réel de chaque agent sur les signaux résolus
  · trouver le seuil d'émission qui maximise le R TOTAL
  · couper les couples (instrument × timeframe) à espérance négative
  · refuser doublons et contradictions

IL NE FAIT PAS :
  · transformer une stratégie perdante en stratégie gagnante. Si les
    agents n'apportent aucune information, aucune pondération ne créera
    d'edge. Le module le dira franchement plutôt que d'inventer un score.

Pourquoi on n'optimise PAS le taux de réussite
-----------------------------------------------
Viser « 80 % de signaux validés » est le piège le plus coûteux du métier.
Le moyen le plus simple d'atteindre 80 % est de rapprocher le TP de
l'entrée : on gagne souvent, très peu, et une seule perte efface dix gains.
On peut atteindre 95 % de réussite avec un système qui ruine un compte.

Ce qui se pilote, c'est l'ESPÉRANCE : taux × gain moyen − (1−taux) × perte.
Le module optimise le R total. Le taux de réussite est un sous-produit
qu'on affiche, jamais une cible qu'on poursuit.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

# --------------------------------------------------------------------------
N_MIN_COMBO = 20          # résolus requis pour juger un couple instrument×tf
N_MIN_AGENT = 30          # résolus requis pour pondérer un agent
N_MIN_SEUIL = 50          # résolus requis pour fixer un seuil d'émission
FENETRE_DOUBLON_MIN = 30  # minutes — deux signaux du même instrument
SL_MIN_ATR = 1.0          # un stop sous 1 ATR est du bruit, pas une invalidation
POIDS_MIN, POIDS_MAX = 0.1, 3.0   # bornes du poids RELATIF d'un agent


# --------------------------------------------------------------------------
@dataclass
class Signal:
    id: str
    instrument: str
    marche: str
    tf: str
    sens: str                      # "achat" | "vente"
    entree: float
    sl: float
    tp: float
    note: float                    # confiance 0..1 au moment de l'émission
    cree_ts: int
    statut: str                    # "TP" | "SL" | "en_attente" | "expire"
    agents: dict[str, str] = field(default_factory=dict)   # code -> avis
    atr: float | None = None       # ATR du timeframe à l'émission
    # Rempli par le suivi de prix après la résolution :
    extreme_favorable: float | None = None   # meilleur prix atteint
    tp_atteint_apres_sl: bool = False        # le TP a-t-il été touché ensuite ?

    @property
    def resolu(self) -> bool:
        return self.statut in ("TP", "SL")

    @property
    def risque(self) -> float:
        return abs(self.entree - self.sl)

    @property
    def rr(self) -> float:
        r = self.risque
        return abs(self.tp - self.entree) / r if r else 0.0

    @property
    def r_realise(self) -> float | None:
        if self.statut == "TP":
            return self.rr
        if self.statut == "SL":
            return -1.0
        return None

    @property
    def sl_en_atr(self) -> float | None:
        return self.risque / self.atr if self.atr else None


# ==========================================================================
# 1. AUDIT DES STOPS — la brique qui manque le plus
# ==========================================================================
@dataclass
class DiagnosticSL:
    cause: str          # "stop_trop_serre" | "direction_fausse" | "indetermine"
    detail: str
    correction: str


def auditer_sl(s: Signal) -> DiagnosticSL:
    """Pourquoi ce stop a-t-il sauté ?

    C'est LA question que le système ne se pose jamais, et c'est pour ça
    qu'il ne s'améliore pas. Deux pannes très différentes se cachent
    derrière un même "SL" :

      · STOP TROP SERRÉ — la direction était bonne, le prix a touché le
        stop puis est allé au TP. L'analyse avait raison, le placement du
        stop avait tort. Correction : élargir le stop, pas changer l'analyse.

      · DIRECTION FAUSSE — le prix est parti et n'est jamais revenu.
        L'analyse avait tort. Correction : revoir les conditions d'entrée.

    Les traiter de la même façon, c'est corriger l'analyse quand le
    problème est le stop, et inversement. C'est ainsi qu'un système
    tourne en rond pendant des mois.
    """
    if s.statut != "SL":
        return DiagnosticSL("sans_objet", "", "")

    if s.tp_atteint_apres_sl:
        n = s.sl_en_atr
        d = f"stop à {n:.2f} ATR" if n else "ATR inconnu"
        return DiagnosticSL(
            "stop_trop_serre",
            f"le TP a été atteint APRÈS le stop — {d}",
            f"élargir le stop à ≥ {SL_MIN_ATR} ATR au-delà du niveau structurel")

    if s.sl_en_atr is not None and s.sl_en_atr < SL_MIN_ATR:
        return DiagnosticSL(
            "stop_trop_serre",
            f"stop à {s.sl_en_atr:.2f} ATR — sous le bruit du timeframe",
            f"stop minimum {SL_MIN_ATR} ATR + le spread")

    # Le prix n'a jamais donné signe de vie dans le bon sens.
    if s.extreme_favorable is not None:
        progres = abs(s.extreme_favorable - s.entree) / s.risque
        if progres < 0.25:
            return DiagnosticSL(
                "direction_fausse",
                f"le prix n'a progressé que de {progres:.2f} R avant le stop",
                "revoir les conditions d'entrée de ce setup")

    return DiagnosticSL("indetermine", "données de suivi insuffisantes",
                        "enregistrer l'extrême favorable et l'ATR à l'émission")


def rapport_stops(signaux: list[Signal]) -> dict:
    sl = [s for s in signaux if s.statut == "SL"]
    if not sl:
        return {"n": 0}
    causes = defaultdict(int)
    for s in sl:
        causes[auditer_sl(s).cause] += 1
    atr = [s.sl_en_atr for s in sl if s.sl_en_atr is not None]
    return {
        "n": len(sl),
        "causes": dict(causes),
        "part_stop_trop_serre": causes["stop_trop_serre"] / len(sl),
        "sl_median_en_atr": sorted(atr)[len(atr) // 2] if atr else None,
        "sous_1_atr": sum(1 for a in atr if a < SL_MIN_ATR) / len(atr) if atr else None,
    }


# ==========================================================================
# 2. CALIBRATION — la note de confiance dit-elle la vérité ?
# ==========================================================================
def courbe_calibration(signaux: list[Signal], n_tranches: int = 5) -> list[dict]:
    """Par tranche de note : taux de réussite RÉEL et R moyen.

    Un système calibré gagne ~40 % des signaux notés 40 %. Si les signaux
    notés 40 % gagnent 20 %, la note ment — et tout ce qui s'appuie dessus
    (seuil d'émission, taille de position, priorité d'affichage) est faux.
    C'est le premier contrôle à faire, avant toute autre optimisation.
    """
    res = [s for s in signaux if s.resolu]
    if not res:
        return []
    out = []
    for i in range(n_tranches):
        lo, hi = i / n_tranches, (i + 1) / n_tranches
        gr = [s for s in res if lo <= s.note < hi or (i == n_tranches - 1 and s.note == 1.0)]
        if not gr:
            continue
        gagnants = sum(1 for s in gr if s.statut == "TP")
        out.append({
            "tranche": f"{lo:.0%}–{hi:.0%}",
            "n": len(gr),
            "note_moyenne": sum(s.note for s in gr) / len(gr),
            "taux_reel": gagnants / len(gr),
            "r_moyen": sum(s.r_realise for s in gr) / len(gr),
            "fiable": len(gr) >= N_MIN_COMBO,
        })
    return out


def ecart_calibration(signaux: list[Signal]) -> float | None:
    """Écart moyen |note annoncée − taux réel|, pondéré par l'effectif.
    Au-delà de 0,15 la note n'est pas exploitable comme probabilité."""
    c = [t for t in courbe_calibration(signaux) if t["fiable"]]
    if not c:
        return None
    n = sum(t["n"] for t in c)
    return sum(abs(t["note_moyenne"] - t["taux_reel"]) * t["n"] for t in c) / n


# ==========================================================================
# 3. POIDS DES AGENTS — mesurés, jamais choisis
# ==========================================================================
def poids_agents(signaux: list[Signal]) -> dict[str, dict]:
    """Pour chaque agent : son avis était-il du bon côté ?

    On compare l'avis de l'agent au sens du signal, et on regarde le
    résultat. Un agent qui vote "haussier" sur des achats qui finissent
    en TP est informatif. Un agent qui vote pareil partout ne l'est pas,
    même s'il a souvent raison : il n'apporte aucune discrimination.

    Le poids est RELATIF : borné à 3× celui d'un agent neutre. Une
    conviction affichée reste 0–100 % — c'est une probabilité, elle ne
    peut pas dépasser 100. Mais un agent peut peser 3 fois plus qu'un
    autre dans le vote. C'est ça, "booster" un agent.
    """
    res = [s for s in signaux if s.resolu]
    stats: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "accords": 0, "r_accord": 0.0, "r_desaccord": 0.0,
                 "n_accord": 0, "n_desaccord": 0, "avis": defaultdict(int)})

    for s in res:
        attendu = "haussier" if s.sens == "achat" else "baissier"
        for code, avis in s.agents.items():
            if avis == "neutre":
                continue
            st = stats[code]
            st["n"] += 1
            st["avis"][avis] += 1
            if avis == attendu:
                st["accords"] += 1
                st["n_accord"] += 1
                st["r_accord"] += s.r_realise
            else:
                st["n_desaccord"] += 1
                st["r_desaccord"] += s.r_realise

    out = {}
    for code, st in stats.items():
        if st["n"] < N_MIN_AGENT:
            out[code] = {"n": st["n"], "poids": 1.0, "fiable": False,
                         "note": "échantillon insuffisant — poids neutre"}
            continue

        r_a = st["r_accord"] / st["n_accord"] if st["n_accord"] else 0.0
        r_d = st["r_desaccord"] / st["n_desaccord"] if st["n_desaccord"] else 0.0
        # Le pouvoir discriminant : l'écart de R entre "d'accord" et
        # "pas d'accord". C'est ce qui mesure l'apport réel de l'agent.
        discrimination = r_a - r_d

        # Un agent qui dit toujours la même chose n'apporte rien, quelle
        # que soit sa réussite apparente.
        total = sum(st["avis"].values())
        variete = 1 - max(st["avis"].values()) / total if total else 0.0
        if variete < 0.10:
            out[code] = {"n": st["n"], "poids": POIDS_MIN, "fiable": True,
                         "discrimination": round(discrimination, 3),
                         "note": "vote quasiment toujours pareil — sans valeur"}
            continue

        poids = max(POIDS_MIN, min(POIDS_MAX, 1.0 + discrimination))
        out[code] = {
            "n": st["n"], "poids": round(poids, 2), "fiable": True,
            "taux_accord": round(st["accords"] / st["n"], 3),
            "r_si_accord": round(r_a, 3), "r_si_desaccord": round(r_d, 3),
            "discrimination": round(discrimination, 3),
            "variete": round(variete, 2),
            "note": ("utile" if discrimination > 0.15 else
                     "contre-indicateur — inverser son vote" if discrimination < -0.15
                     else "sans pouvoir discriminant"),
        }
    return out


# ==========================================================================
# 4. ESPÉRANCE PAR COUPLE — qui a le droit d'émettre
# ==========================================================================
def esperance_par_combo(signaux: list[Signal]) -> dict[tuple, dict]:
    g = defaultdict(list)
    for s in signaux:
        if s.resolu:
            g[(s.instrument, s.tf)].append(s)
    out = {}
    for cle, lot in g.items():
        r = [s.r_realise for s in lot]
        tp = sum(1 for s in lot if s.statut == "TP")
        esp = sum(r) / len(r)
        out[cle] = {
            "n": len(lot), "r_total": round(sum(r), 2),
            "esperance": round(esp, 3), "taux": round(tp / len(lot), 3),
            "fiable": len(lot) >= N_MIN_COMBO,
            "verdict": ("AUTORISE" if (len(lot) >= N_MIN_COMBO and esp > 0)
                        else "COUPE" if len(lot) >= N_MIN_COMBO
                        else "OBSERVATION"),
        }
    return out


# ==========================================================================
# 5. LE SEUIL D'ÉMISSION — par le R total, jamais par le taux
# ==========================================================================
def seuil_optimal(signaux: list[Signal], pas: float = 0.05) -> dict:
    """Balaye les seuils de note et retient celui qui maximise le R total.

    Renvoie honnêtement `rentable: False` si AUCUN seuil ne rend le
    système positif. C'est l'issue la plus probable d'un système qui perd,
    et c'est une information bien plus utile qu'un seuil inventé.
    """
    res = [s for s in signaux if s.resolu]
    if len(res) < N_MIN_SEUIL:
        return {"assez_de_donnees": False, "n": len(res),
                "message": f"{len(res)} résolus, il en faut {N_MIN_SEUIL}"}

    courbe = []
    x = 0.0
    while x <= 0.95:
        gardes = [s for s in res if s.note >= x]
        if len(gardes) >= N_MIN_COMBO:
            r = sum(s.r_realise for s in gardes)
            tp = sum(1 for s in gardes if s.statut == "TP")
            courbe.append({"seuil": round(x, 2), "n": len(gardes),
                           "r_total": round(r, 2),
                           "esperance": round(r / len(gardes), 3),
                           "taux": round(tp / len(gardes), 3)})
        x += pas

    if not courbe:
        return {"assez_de_donnees": False, "n": len(res),
                "message": "aucun seuil ne garde assez de signaux"}

    meilleur = max(courbe, key=lambda c: c["r_total"])
    return {
        "assez_de_donnees": True,
        "rentable": meilleur["r_total"] > 0,
        "seuil": meilleur["seuil"],
        "r_total_attendu": meilleur["r_total"],
        "esperance": meilleur["esperance"],
        "taux_attendu": meilleur["taux"],
        "signaux_gardes": meilleur["n"],
        "signaux_total": len(res),
        "part_gardee": round(meilleur["n"] / len(res), 3),
        "courbe": courbe,
        "message": (
            f"seuil {meilleur['seuil']:.0%} → {meilleur['r_total']:+.1f}R "
            f"sur {meilleur['n']} signaux"
            if meilleur["r_total"] > 0 else
            "AUCUN seuil ne rend le système positif — le problème n'est pas "
            "le filtrage, c'est la stratégie elle-même"),
    }


# ==========================================================================
# 6. LES GARDE-FOUS D'ÉMISSION
# ==========================================================================
def filtrer_emission(candidats: list[Signal], seuil: float,
                     combos: dict[tuple, dict]) -> tuple[list[Signal], list[dict]]:
    """Applique les règles dans l'ordre. Retourne (gardés, refusés+motif)."""
    gardes: list[Signal] = []
    refuses: list[dict] = []

    def refuser(s: Signal, motif: str) -> None:
        refuses.append({"id": s.id, "instrument": s.instrument, "tf": s.tf,
                        "motif": motif})

    for s in sorted(candidats, key=lambda x: -x.note):
        if s.note < seuil:
            refuser(s, f"note {s.note:.0%} sous le seuil {seuil:.0%}")
            continue

        v = combos.get((s.instrument, s.tf), {}).get("verdict", "OBSERVATION")
        if v == "COUPE":
            refuser(s, f"{s.instrument} {s.tf} : espérance négative mesurée")
            continue

        if s.sl_en_atr is not None and s.sl_en_atr < SL_MIN_ATR:
            refuser(s, f"stop à {s.sl_en_atr:.2f} ATR — sous le bruit")
            continue

        # Contradiction : même instrument, sens opposé, déjà retenu.
        contra = next((g for g in gardes
                       if g.instrument == s.instrument and g.sens != s.sens), None)
        if contra:
            refuser(s, f"contredit le signal {contra.tf} déjà retenu "
                       f"({contra.sens} vs {s.sens})")
            continue

        # Doublon : même instrument, même sens, fenêtre courte.
        doublon = next((g for g in gardes
                        if g.instrument == s.instrument and g.sens == s.sens
                        and abs(g.cree_ts - s.cree_ts) < FENETRE_DOUBLON_MIN * 60), None)
        if doublon:
            refuser(s, f"doublon de {doublon.tf} (< {FENETRE_DOUBLON_MIN} min)")
            continue

        gardes.append(s)
    return gardes, refuses


# ==========================================================================
# 7. LE RAPPORT
# ==========================================================================
def bilan(signaux: list[Signal]) -> dict:
    res = [s for s in signaux if s.resolu]
    tp = [s for s in res if s.statut == "TP"]
    sl = [s for s in res if s.statut == "SL"]
    gains = sum(s.r_realise for s in tp)
    pertes = -sum(s.r_realise for s in sl)
    return {
        "emis": len(signaux), "resolus": len(res),
        "jamais_entres": len(signaux) - len(res),
        "tp": len(tp), "sl": len(sl),
        "taux": round(len(tp) / len(res), 3) if res else None,
        "r_total": round(gains - pertes, 2),
        "esperance": round((gains - pertes) / len(res), 3) if res else None,
        "profit_factor": round(gains / pertes, 2) if pertes else None,
        "gain_moyen": round(gains / len(tp), 2) if tp else None,
        "taux_equilibre": round(1 / (1 + gains / len(tp)), 3) if tp else None,
    }


def rapport(signaux: list[Signal]) -> str:
    b = bilan(signaux)
    st = rapport_stops(signaux)
    seuil = seuil_optimal(signaux)
    ec = ecart_calibration(signaux)
    L = "=" * 74
    o = [L, "  SUPERVISEUR — AUTO-DIAGNOSTIC", L, ""]

    # Un journal sans signal résolu n'est pas une erreur : c'est l'état
    # normal d'un système qui vient de démarrer. Le module doit le dire,
    # pas planter sur un formatage.
    if not b["resolus"]:
        o += [f"  {b['emis']} signal(aux) émis, aucun résolu pour l'instant.",
              "  Rien à calibrer tant qu'un signal n'a pas touché son TP",
              "  ou son SL — un signal jamais entré n'apprend rien.", ""]
        return "\n".join(o)

    o.append(f"  {b['r_total']:+.1f}R sur {b['resolus']} résolus "
             f"({b['emis']} émis, {b['jamais_entres']} jamais entrés)")
    o.append(f"  taux {b['taux']:.1%} · gain moyen +{b['gain_moyen']}R · "
             f"équilibre à {b['taux_equilibre']:.1%}")
    if b["esperance"] is not None and b["esperance"] < 0:
        manque = b["taux_equilibre"] - b["taux"]
        o.append(f"  ⚠ espérance {b['esperance']:+.3f}R — il manque "
                 f"{manque:.1%} points de réussite pour l'équilibre")

    o += ["", "  STOPS"]
    if st["n"]:
        o.append(f"    {st['n']} stops touchés · "
                 f"{st['part_stop_trop_serre']:.0%} par stop trop serré")
        if st["sl_median_en_atr"]:
            o.append(f"    stop médian : {st['sl_median_en_atr']:.2f} ATR"
                     + (f" · {st['sous_1_atr']:.0%} sous {SL_MIN_ATR} ATR"
                        if st["sous_1_atr"] else ""))
        for c, n in sorted(st["causes"].items(), key=lambda x: -x[1]):
            o.append(f"      {c:<20} {n}")

    o += ["", "  CALIBRATION DE LA NOTE"]
    for t in courbe_calibration(signaux):
        marque = "" if t["fiable"] else "  (n trop faible)"
        o.append(f"    {t['tranche']:<10} n={t['n']:<4} annoncé "
                 f"{t['note_moyenne']:.0%} → réel {t['taux_reel']:.0%} · "
                 f"{t['r_moyen']:+.2f}R{marque}")
    if ec is not None:
        verdict = "exploitable" if ec <= 0.15 else "NON exploitable comme probabilité"
        o.append(f"    écart moyen {ec:.1%} — {verdict}")

    o += ["", "  AGENTS (poids mesuré, pas choisi)"]
    for code, a in sorted(poids_agents(signaux).items(),
                          key=lambda x: -x[1].get("discrimination", 0)):
        if not a["fiable"]:
            o.append(f"    {code}  n={a['n']:<4} poids ×1.00   {a['note']}")
        else:
            o.append(f"    {code}  n={a['n']:<4} poids ×{a['poids']:.2f}   "
                     f"discr. {a['discrimination']:+.2f}   {a['note']}")

    o += ["", "  COUPLES INSTRUMENT × TIMEFRAME"]
    combos = esperance_par_combo(signaux)
    for cle, c in sorted(combos.items(), key=lambda x: -x[1]["esperance"]):
        if c["fiable"]:
            o.append(f"    {cle[0]:<10} {cle[1]:<5} n={c['n']:<4} "
                     f"{c['esperance']:+.3f}R  {c['verdict']}")

    o += ["", "  SEUIL D'ÉMISSION", f"    {seuil.get('message', '')}"]
    if seuil.get("assez_de_donnees") and not seuil.get("rentable"):
        o += ["",
              "    Aucun filtrage ne sauve ce système. Filtrer plus fort ne",
              "    fait que perdre moins vite. Il faut corriger les stops et",
              "    les conditions d'entrée avant de rechercher un seuil."]
    o.append("")
    return "\n".join(o)


# ==========================================================================
def charger_journal(chemin: str | Path) -> list[Signal]:
    d = json.loads(Path(chemin).read_text())
    champs = Signal.__dataclass_fields__.keys()
    return [Signal(**{k: v for k, v in x.items() if k in champs}) for x in d]


if __name__ == "__main__":
    import sys, random
    if len(sys.argv) > 1:
        print(rapport(charger_journal(sys.argv[1])))
        sys.exit(0)

    # Démonstration : un jeu qui reproduit les statistiques réelles
    # observées (23,6 % de réussite, gain moyen +2,09R, −78R).
    rng = random.Random(4)
    sig, t = [], 1_750_000_000
    for i in range(548):
        inst = rng.choice(["XAUUSD", "XAGUSD", "CUIVRE", "BTCUSD", "GDX"])
        tf = rng.choice(["M5", "M15", "M30"])
        note = rng.uniform(0.20, 0.50)
        atr = 10.0
        serre = rng.random() < 0.55
        risque = atr * (rng.uniform(0.3, 0.8) if serre else rng.uniform(1.0, 2.0))
        entree = 100.0
        sens = rng.choice(["achat", "vente"])
        s = Signal(id=f"s{i}", instrument=inst, marche="matieres", tf=tf,
                   sens=sens, entree=entree,
                   sl=entree - risque if sens == "achat" else entree + risque,
                   tp=entree + 2.1 * risque if sens == "achat" else entree - 2.1 * risque,
                   note=note, cree_ts=t + i * 900, statut="en_attente", atr=atr,
                   agents={f"AG-{c:02d}": rng.choice(["haussier", "baissier", "neutre"])
                           for c in (1, 2, 3, 9, 10)})
        u = rng.random()
        if u < 0.47:
            s.statut = "en_attente"
        else:
            s.statut = "TP" if rng.random() < 0.236 else "SL"
            if s.statut == "SL":
                s.tp_atteint_apres_sl = serre and rng.random() < 0.45
                s.extreme_favorable = entree + rng.uniform(0, 0.4) * risque * (
                    1 if sens == "achat" else -1)
        sig.append(s)
    print(rapport(sig))
