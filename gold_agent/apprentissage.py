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
    resolus = [x for x in entrees if x["statut"] in ("gagnant", "perdant")]
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

    sig = signaux()
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
    if ecrits:
        ETAT.write_text(json.dumps({"jour": jour, "resolus": resolus}))
    return ecrits
