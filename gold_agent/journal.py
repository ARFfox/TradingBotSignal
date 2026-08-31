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


def cle_signal(tf: str, s: dict) -> str:
    return f"{tf}|{s['setup']}|{s['entree']}|{s['stop']}|{s['objectif']}"


def enregistrer(tf: str, s: dict, prix: float, fiabilite: str) -> bool:
    """Ajoute un signal s'il n'est pas déjà connu. Renvoie True si nouveau."""
    k = cle_signal(tf, s)
    with _VERROU:
        signaux = _charger()
        # Deduplication sur la cle QUEL QUE SOIT le statut : un signal deja
        # tranche (perdant/gagnant) qui reste affiche par la regle n'est pas
        # une nouvelle configuration — le recompter gonflerait l'historique
        # du meme trade repete toutes les 10 secondes.
        if any(x["cle"] == k for x in signaux):
            return False
        signaux.append({
            "cle": k, "tf": tf, "sens": s["setup"],
            "entree": s["entree"], "stop": s["stop"], "objectif": s["objectif"],
            "rr_prevu": s.get("rr"), "fiabilite": fiabilite,
            "prix_a_l_emission": prix,
            "cree_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "cree_ts": int(dt.datetime.now(dt.timezone.utc).timestamp()),
            "statut": "en_attente",     # -> ouvert -> gagnant/perdant ; ou non_execute
            "resolu_le": None, "r_obtenu": None,
        })
        _sauver(signaux)
    return True


def resoudre(bars_par_tf: dict) -> int:
    """Fait avancer chaque signal ouvert avec les bougies disponibles.

    `bars_par_tf` : {"H4": [...], ...} — les bougies deja en cache du
    tableau ; aucune requete supplementaire n'est faite ici.
    """
    maintenant = int(dt.datetime.now(dt.timezone.utc).timestamp())
    modifies = 0
    with _VERROU:
        signaux = _charger()
        for s in signaux:
            if s["statut"] not in ("en_attente", "ouvert"):
                continue
            bars = bars_par_tf.get(s["tf"]) or []
            apres = [b for b in bars if b["time"] > s["cree_ts"]]
            if not apres:
                continue
            achat = s["sens"] == "achat"

            if s["statut"] == "en_attente":
                for b in apres:
                    touche = (b["low"] <= s["entree"]) if achat else (b["high"] >= s["entree"])
                    if touche:
                        s["statut"] = "ouvert"
                        s["ouvert_ts"] = b["time"]
                        modifies += 1
                        break
                if s["statut"] == "en_attente" and \
                        maintenant - s["cree_ts"] > DELAI_EXECUTION_H * 3600:
                    s["statut"] = "non_execute"
                    s["resolu_le"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                    modifies += 1
                    continue

            if s["statut"] == "ouvert":
                for b in apres:
                    if b["time"] < s.get("ouvert_ts", s["cree_ts"]):
                        continue
                    stop = (b["low"] <= s["stop"]) if achat else (b["high"] >= s["stop"])
                    obj = (b["high"] >= s["objectif"]) if achat else (b["low"] <= s["objectif"])
                    if stop:        # bougie ambigue -> perte, comme au backtest
                        s["statut"], s["r_obtenu"] = "perdant", -1.0
                    elif obj:
                        s["statut"], s["r_obtenu"] = "gagnant", s.get("rr_prevu")
                    else:
                        continue
                    s["resolu_le"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                    modifies += 1
                    break
        if modifies:
            _sauver(signaux)
    return modifies


def statistiques() -> dict:
    signaux = _charger()
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
