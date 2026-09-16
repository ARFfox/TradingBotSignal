"""Adaptateur journal → Superviseur apprenant (CHANTIER étapes 4-5).

Les modules livrés (`superviseur_apprenant`, `chercheur_sous_ensembles`)
parlent en `Signal` ; le journal parle en dictionnaires. Ce fichier fait
UNIQUEMENT la traduction et l'écriture des deux rapports — aucun calcul
d'apprentissage ne vit ici (il vit dans les modules livrés, testés).

Cadence (SPEC_SUPERVISEUR_AUTONOME) : une écriture par jour, OU dès que
20 nouveaux signaux résolus se sont accumulés depuis la dernière —
apprendre sur 3 nouveaux trades serait du bruit.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:                     # modules livrés à la racine
    sys.path.insert(0, str(RACINE))

RAPPORT_SUPERVISEUR = RACINE / "rapport_superviseur.md"
RAPPORT_SOUS_ENSEMBLES = RACINE / "rapport_sous_ensembles.md"
RAPPORT_PIPS = RACINE / "rapport_pips.md"
RAPPORT_AVOCATS = RACINE / "rapport_avocats.md"
POIDS_AVOCATS = Path.home() / ".gold_agent_poids_avocats.json"
CALIBRAGE = Path.home() / ".gold_agent_calibrage.json"
HISTORIQUE_CALIBRATION = RACINE / "historique_calibration.json"
ETAT = Path.home() / ".gold_agent_apprentissage.json"
NOUVEAUX_RESOLUS_MIN = 20

# journal -> dataclass Signal : les statuts et avis n'ont pas le même
# vocabulaire des deux côtés, la traduction est LA raison d'être du module.
_STATUTS = {"gagnant": "TP", "perdant": "SL", "non_execute": "expire",
            "en_attente": "en_attente", "ouvert": "en_attente"}
_AVIS = {"achat": "haussier", "vente": "baissier"}


def _marche(symbole: str) -> str:
    from . import instruments
    for inst in instruments.REGISTRE.values():
        if inst.symbole == symbole:
            return inst.marche
    return "matieres"


def signaux(entrees: list[dict] | None = None) -> list:
    """Le journal brut → liste de `Signal` du module livré."""
    from superviseur_apprenant import Signal
    from . import instruments, journal
    if entrees is None:
        entrees = journal._charger()
    defaut = instruments.par_defaut().symbole
    marches: dict[str, str] = {}
    out = []
    for x in entrees:
        try:
            # Artefacts de l'ancien arrondi 2 décimales (corrigé le 15/09) :
            # entrée==SL ou entrée==TP -> risque ou gain nul, aucun trade
            # réel ne ressemble à ça. Exclus de l'apprentissage ET des pips ;
            # le journal brut les garde (données, pas jugement).
            if x["entree"] in (x["stop"], x["objectif"]):
                continue
            inst = x.get("instrument") or defaut
            if inst not in marches:
                marches[inst] = _marche(inst)
            note = x.get("decision_chef")
            out.append(Signal(
                id=x["cle"], instrument=inst, marche=marches[inst],
                tf=x["tf"], sens=x["sens"], entree=x["entree"],
                sl=x["stop"], tp=x["objectif"],
                # les vieux signaux sans note du Superviseur comptent 50 %
                note=(note if note is not None else 50) / 100.0,
                cree_ts=x.get("cree_ts", 0),
                statut=_STATUTS.get(x["statut"], "en_attente"),
                agents={c: _AVIS.get(a, "neutre")
                        for c, a in (x.get("avis") or {}).items()},
                atr=x.get("atr"),
                extreme_favorable=x.get("extreme_favorable"),
                tp_atteint_apres_sl=bool(x.get("tp_atteint_apres_sl")),
            ))
        except Exception:
            continue                    # une entrée corrompue ne bloque rien
    return out


def equilibre(entrees: list[dict] | None = None) -> dict | None:
    """La ligne d'équilibre de l'onglet Signaux validés : à quel taux le
    système ne perd plus, compte tenu de son gain moyen RÉEL. C'est LA
    référence honnête — jamais 50 %."""
    from . import journal
    if entrees is None:
        entrees = journal._charger()
    resolus = [x for x in entrees if x["statut"] in ("gagnant", "perdant")
               and x["entree"] not in (x["stop"], x["objectif"])]
    gagnants = [x for x in resolus if x["statut"] == "gagnant"]
    rrs = [x.get("rr_prevu") for x in resolus if x.get("rr_prevu")]
    if not resolus or not rrs:
        return None
    gain_moyen = sum(rrs) / len(rrs)
    taux_equilibre = 100.0 / (1.0 + gain_moyen)
    taux = len(gagnants) / len(resolus) * 100.0
    return {"gain_moyen": round(gain_moyen, 2),
            "equilibre_pct": round(taux_equilibre, 1),
            "taux_pct": round(taux, 1),
            "ecart_pts": round(taux - taux_equilibre, 1),
            "resolus": len(resolus)}


def _calibration_avocats(entrees: list[dict]) -> tuple[str, dict] | None:
    """Rejoue les plaidoiries sur les signaux résolus dont le contexte a
    été journalisé, et mesure le poids réel de chaque argument. Renvoie
    (texte du rapport, {code: poids}) — None tant que rien n'est mesurable."""
    from avocats import Contexte, calibrer, rapport_calibration
    paires = []
    for x in entrees:
        ctx_d = (x.get("debat") or {}).get("ctx")
        if not ctx_d or x["statut"] not in ("gagnant", "perdant"):
            continue
        sig = signaux([x])
        if not sig:
            continue
        try:
            paires.append((sig[0], Contexte(**ctx_d)))
        except Exception:
            continue
    if not paires:
        return None
    poids = calibrer(paires)
    return rapport_calibration(poids), {k: v.poids for k, v in poids.items()}


def calibrage_actuel() -> dict:
    """La dernière calibration persistée par la boucle 24 h : poids des
    agents (0,1×–3×), verdicts par couple (AUTORISE/COUPE/OBSERVATION),
    seuil d'émission mesuré. Vide tant que rien n'a tourné."""
    if CALIBRAGE.exists():
        try:
            return json.loads(CALIBRAGE.read_text())
        except Exception:
            pass
    return {}


def refus_calibrage(instrument: str, tf: str, note_pct: float) -> str | None:
    """SPEC §2.5 règles 1-2, sur la calibration MESURÉE : couple à
    espérance négative (>= 20 résolus) refusé ; note sous le seuil refusée
    UNIQUEMENT si `seuil_optimal` a trouvé un seuil rentable — il a le
    droit de répondre « aucun », et alors rien ne filtre sur la note."""
    c = calibrage_actuel()
    combo = (c.get("combos") or {}).get(f"{instrument}|{tf}")
    if combo and combo.get("verdict") == "COUPE":
        return (f"couple coupé : {combo.get('esperance'):+.2f}R mesuré "
                f"sur {combo.get('n')} résolus")
    seuil = c.get("seuil") or {}
    if seuil.get("assez_de_donnees") and seuil.get("rentable") \
            and note_pct / 100.0 < seuil.get("seuil", 0.0):
        return (f"note {note_pct:.0f}% sous le seuil mesuré "
                f"{seuil['seuil']:.0%} ({seuil.get('message', '')[:40]})")
    return None


def _persister_calibrage(sig: list, resolus: int) -> None:
    """Étapes 4-6 de la boucle (SPEC §4) : poids, couples, seuil — bornés
    par les modules eux-mêmes. Chaque changement part dans
    historique_calibration.json (avant, après, effectif) : réversible."""
    import superviseur_apprenant as sup
    poids = sup.poids_agents(sig)
    combos = {f"{k[0]}|{k[1]}": v for k, v in sup.esperance_par_combo(sig).items()}
    seuil = sup.seuil_optimal(sig)
    seuil.pop("courbe", None)                    # trop lourd pour l'état
    nouveau = {"jour": dt.date.today().isoformat(), "resolus": resolus,
               "poids_agents": poids, "combos": combos, "seuil": seuil}
    ancien = calibrage_actuel()

    changements = []
    for code, p in poids.items():
        av = ((ancien.get("poids_agents") or {}).get(code) or {}).get("poids")
        if av != p["poids"]:
            changements.append({"quoi": f"poids {code}", "avant": av,
                                "apres": p["poids"], "effectif": p["n"]})
    for cle, v in combos.items():
        av = ((ancien.get("combos") or {}).get(cle) or {}).get("verdict")
        if av != v["verdict"]:
            changements.append({"quoi": f"couple {cle}", "avant": av,
                                "apres": v["verdict"], "effectif": v["n"]})
    av_s = (ancien.get("seuil") or {}).get("seuil")
    if av_s != seuil.get("seuil"):
        changements.append({"quoi": "seuil d'émission", "avant": av_s,
                            "apres": seuil.get("seuil"),
                            "effectif": seuil.get("n",
                                                  seuil.get("signaux_total"))})
    if changements:
        histo = []
        if HISTORIQUE_CALIBRATION.exists():
            try:
                histo = json.loads(HISTORIQUE_CALIBRATION.read_text())
            except Exception:
                histo = []
        horodate = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        histo.extend({**c, "date": horodate} for c in changements)
        HISTORIQUE_CALIBRATION.write_text(
            json.dumps(histo, ensure_ascii=False, indent=1))
    CALIBRAGE.write_text(json.dumps(nouveau, ensure_ascii=False, indent=1))


def _charger_etat() -> dict:
    if ETAT.exists():
        try:
            return json.loads(ETAT.read_text())
        except Exception:
            pass
    return {}


def rapports_si_du(force: bool = False) -> list[str]:
    """Écrit rapport_superviseur.md et rapport_sous_ensembles.md si c'est
    l'heure (nouveau jour OU ≥ 20 nouveaux résolus). Renvoie les chemins
    écrits — vide si rien n'était dû."""
    import superviseur_apprenant as sup
    import chercheur_sous_ensembles as che
    from . import journal

    entrees = journal._charger()
    sig = signaux(entrees)
    resolus = sum(1 for s in sig if s.resolu)
    etat = _charger_etat()
    jour = dt.date.today().isoformat()
    if not force and etat.get("jour") == jour \
            and resolus - etat.get("resolus", 0) < NOUVEAUX_RESOLUS_MIN:
        return []

    horodatage = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entete = (f"généré le {horodatage} · {len(sig)} signaux au journal · "
              f"{resolus} résolus\n\n")
    ecrits = []
    try:
        RAPPORT_SUPERVISEUR.write_text(
            "# Rapport du Superviseur apprenant\n\n" + entete
            + "```\n" + sup.rapport(sig) + "\n```\n")
        ecrits.append(str(RAPPORT_SUPERVISEUR))
    except Exception:
        pass
    try:
        RAPPORT_SOUS_ENSEMBLES.write_text(
            "# Chasse aux sous-ensembles\n\n" + entete
            + "```\n" + che.rapport(sig) + "\n```\n")
        ecrits.append(str(RAPPORT_SOUS_ENSEMBLES))
    except Exception:
        pass
    try:
        import pips
        RAPPORT_PIPS.write_text(
            "# Bilan en pips\n\n" + entete
            + "```\n" + pips.rapport(pips.bilan(sig)) + "\n```\n")
        ecrits.append(str(RAPPORT_PIPS))
    except Exception:
        pass
    # Le débat apprend : les poids mesurés repartent vers l'émission via
    # debat.poids_arguments() — un argument « à retourner » reste affiché,
    # jamais supprimé (c'est un contre-indicateur, donc une information).
    try:
        cal = _calibration_avocats(entrees)
        if cal:
            texte_cal, poids = cal
            RAPPORT_AVOCATS.write_text(
                "# Calibration du débat contradictoire\n\n" + entete + texte_cal)
            POIDS_AVOCATS.write_text(json.dumps(poids))
            ecrits.append(str(RAPPORT_AVOCATS))
    except Exception:
        pass
    # SPEC §4 étapes 4-6 : la calibration (poids, couples, seuil) est
    # recalculée et persistée à la même cadence que les rapports — c'est
    # elle que decision.noter et l'émission relisent.
    try:
        _persister_calibrage(sig, resolus)
    except Exception:
        pass
    if ecrits:
        ETAT.write_text(json.dumps({"jour": jour, "resolus": resolus}))
    return ecrits
