"""Journal des signaux : chaque signal émis est enregistré, puis suivi
jusqu'à son dénouement — objectif touché, stop touché, jamais exécuté.

C'est la mémoire qui manquait : sans historique, « ça marche » n'est
qu'une impression. Les règles de résolution sont les mêmes que le
backtest : la bougie ambiguë (stop ET objectif touchés) compte en perte.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path

FICHIER = Path.home() / ".gold_agent_journal.json"
_VERROU = threading.Lock()

DELAI_EXECUTION_H = 48      # entree limite jamais touchee sous 48 h -> abandonne
TF_SECONDES = {"H4": 14400, "H1": 3600, "M30": 1800, "M15": 900, "M5": 300}


def _charger() -> list[dict]:
    if FICHIER.exists():
        try:
            return json.loads(FICHIER.read_text())
        except Exception:
            return []
    return []


def _sauver(signaux: list[dict]) -> None:
    FICHIER.write_text(json.dumps(signaux, ensure_ascii=False, indent=1))


def _defaut() -> str:
    from . import instruments
    return instruments.par_defaut().symbole


def cle_signal(tf: str, s: dict, instrument: str | None = None) -> str:
    """Cle SANS le stop ni l'objectif : ils sont derives de l'ATR et bougent
    de quelques centimes a chaque cycle — les inclure transformait une seule
    configuration en dizaines de « signaux » (167 entrees pour 10 trades
    reels le 31/08). L'entree est arrondie au point entier ; l'instrument
    fait partie de la cle depuis le passage multi-marches (15/09)."""
    inst = instrument or _defaut()
    # les petits prix (forex, alts) s'arrondissent plus finement
    entree = round(s["entree"], 4 if s["entree"] < 100 else 0)
    return f"{inst}|{tf}|{s['setup']}|{entree}"


FENETRE_ANTIRAFALE_H = 12   # pas deux enregistrements du meme groupe sous 12 h


def enregistrer(tf: str, s: dict, prix: float, fiabilite: str,
                instrument: str | None = None,
                atr: float | None = None, spread: float | None = None) -> bool:
    """Ajoute un signal s'il n'est pas déjà connu. Renvoie True si nouveau."""
    instrument = instrument or _defaut()
    k = cle_signal(tf, s, instrument)
    with _VERROU:
        signaux = _charger()
        # Deduplication sur la cle QUEL QUE SOIT le statut : un signal deja
        # tranche (perdant/gagnant) qui reste affiche par la regle n'est pas
        # une nouvelle configuration — le recompter gonflerait l'historique
        # du meme trade repete toutes les 10 secondes.
        maintenant_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())
        for x in signaux:
            if x["cle"] == k and                     maintenant_ts - x["cree_ts"] < FENETRE_ANTIRAFALE_H * 3600:
                return False
        signaux.append({
            "cle": k, "instrument": instrument, "tf": tf, "sens": s["setup"],
            "entree": s["entree"], "stop": s["stop"], "objectif": s["objectif"],
            "rr_prevu": s.get("rr"), "fiabilite": fiabilite,
            "prix_a_l_emission": prix,
            "cree_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "cree_ts": int(dt.datetime.now(dt.timezone.utc).timestamp()),
            "statut": "en_attente",     # -> ouvert -> gagnant/perdant ; ou non_execute
            "resolu_le": None, "r_obtenu": None,
            # Trace du Miroir (AG-10) : indispensable pour mesurer un jour
            # si la confirmation intermarche ameliore reellement les resultats.
            "intermarche": s.get("intermarche"),
            # Avis directionnels des agents a l'emission — la matiere du
            # score de Brier du Chef d'orchestre (poids calcules).
            "avis": s.get("avis") or {},
            # La decision chiffree du Superviseur au moment de l'emission
            "decision_chef": (s.get("decision_chef") or {}).get("pct"),
            # CHANTIER etape 1 : sans atr aucun stop ne peut etre juge ;
            # sans tp_atteint_apres_sl les deux causes de SL sont
            # indiscernables (stop trop serre vs direction fausse).
            "atr": atr, "spread": spread,
            "extreme_favorable": None, "tp_atteint_apres_sl": False,
            "r_realise": None,
            # APPLIQUER etape 6 : le debat AG-16/AG-18 a l'emission —
            # verdict, score, arguments et le contexte qui permettra de
            # calibrer chaque argument sur le resultat reel.
            "debat": s.get("debat"),
            # Étape 6bis / 10 : la direction d'AG-19 (sources comprises) et
            # les figures présentes — la matière des calibrations « source »
            # et « figure » du cerveau.
            "direction": s.get("direction"),
            "figures": s.get("figures"),
            # SPEC_SITE_V3 §7 : le journal ne contient QUE des signaux
            # emis (les suspendus n'y entrent jamais) — le champ le grave.
            "emis": True,
        })
        _sauver(signaux)
    return True


def resoudre(bars_par_tf: dict, instrument: str | None = None) -> int:
    """Fait avancer chaque signal ouvert avec les bougies disponibles.

    `bars_par_tf` : {"H4": [...], ...} — les bougies deja en cache ; aucune
    requete supplementaire ici. `instrument` limite la resolution a UN
    instrument (multi-marches) ; None = l'or (les entrees historiques sans
    champ instrument sont a lui).
    """
    instrument = instrument or _defaut()
    maintenant = int(dt.datetime.now(dt.timezone.utc).timestamp())
    modifies = 0
    with _VERROU:
        signaux = _charger()
        for s in signaux:
            if s["statut"] not in ("en_attente", "ouvert"):
                continue
            if s.get("instrument", _defaut()) != instrument:
                continue
            bars = bars_par_tf.get(s["tf"]) or []
            apres = [b for b in bars if b["time"] > s["cree_ts"]]
            if not apres:
                continue
            # CHANTIER etape 1 : la resolution passe par garde_fous.suivre —
            # meme convention pessimiste (SL d'abord sur bougie ambigue),
            # PLUS le suivi apres SL qui distingue « stop trop serre »
            # (tp_atteint_apres_sl) de « direction fausse »
            # (extreme_favorable proche de l'entree).
            from garde_fous import suivre
            res = suivre({"entree": s["entree"], "sl": s["stop"],
                          "tp": s["objectif"], "sens": s["sens"]}, apres)
            correspondance = {"TP": "gagnant", "SL": "perdant",
                              "expire": "non_execute"}
            nouveau = correspondance.get(res.statut)
            if res.statut == "en_attente" and res.entree_touchee \
                    and s["statut"] == "en_attente":
                s["statut"] = "ouvert"
                modifies += 1
            # l'expiration reste TEMPORELLE (48 h sans entree), pas en
            # nombre de bougies : suivre dit « pas encore », l'horloge tranche
            if nouveau == "non_execute" \
                    and maintenant - s["cree_ts"] <= DELAI_EXECUTION_H * 3600:
                nouveau = None
            if nouveau and nouveau != s["statut"]:
                s["statut"] = nouveau
                s["r_obtenu"] = res.r_realise
                s["r_realise"] = res.r_realise
                s["extreme_favorable"] = res.extreme_favorable
                s["tp_atteint_apres_sl"] = bool(res.tp_atteint_apres_sl)
                s["resolu_le"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                modifies += 1
        if modifies:
            _sauver(signaux)
    return modifies


def statistiques(fenetre_jours: int | None = None) -> dict:
    """Stats du journal. `fenetre_jours` restreint aux signaux recents —
    indispensable pour les criteres de suspension : sans fenetre, une
    vieille serie perdante verrouillait l'emission pour toujours (les
    nouveaux trades etant bloques, le ratio ne pouvait plus bouger)."""
    signaux = _charger()
    if fenetre_jours:
        import time as _t
        seuil = _t.time() - fenetre_jours * 86400
        signaux = [x for x in signaux if x.get("cree_ts", 0) >= seuil]
    resolus = [s for s in signaux if s["statut"] in ("gagnant", "perdant")]
    gagnants = [s for s in resolus if s["statut"] == "gagnant"]
    rs = [s["r_obtenu"] for s in resolus if s.get("r_obtenu") is not None]
    par_tf = {}
    for s in resolus:
        d = par_tf.setdefault(s["tf"], {"gagnants": 0, "perdants": 0})
        d["gagnants" if s["statut"] == "gagnant" else "perdants"] += 1
    return {
        "total_emis": len(signaux),
        "en_attente": sum(1 for s in signaux if s["statut"] == "en_attente"),
        "ouverts": sum(1 for s in signaux if s["statut"] == "ouvert"),
        "non_executes": sum(1 for s in signaux if s["statut"] == "non_execute"),
        "resolus": len(resolus),
        "gagnants": len(gagnants), "perdants": len(resolus) - len(gagnants),
        "taux_reussite_pct": round(len(gagnants) / len(resolus) * 100, 1) if resolus else None,
        "cumul_R": round(sum(rs), 2) if rs else 0.0,
        "par_tf": par_tf,
        "derniers": sorted(signaux, key=lambda x: x["cree_ts"], reverse=True)[:20],
    }
