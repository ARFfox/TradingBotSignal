"""Le cycle du cerveau (APPLIQUER étape 10.1) — `python3 -m taches.cerveau_cycle`.

Toutes les heures (boucle « cerveau » du site, ou à la main) : relit le
journal, fait tourner les CINQ calibrations, et fusionne leurs poids dans
`cerveau.json` — la source unique que le débat, les figures et le Directeur
relisent. Chaque changement est lissé (±0,35/cycle), journalisé et
réversible. Sous 20 résolus NOUVEAUX, rien ne bouge, et c'est voulu.

Écrit aussi `rapport_cerveau.md` : ce qu'il a appris, ce qui le bride.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path


RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

CERVEAU_JSON = RACINE / "cerveau.json"
RAPPORT = RACINE / "rapport_cerveau.md"
_CACHE_AUDITS: dict = {"t": 0.0, "audits": {}, "live": None, "t_live": 0.0}


def _paires_depuis_journal(entrees, sig_par_cle):
    """(paires_avocats, paires_figures, paires_sources) depuis le journal
    brut : seuls les signaux résolus qui portent la trace comptent."""
    from avocats import Contexte
    from direction import Source
    p_avocats, p_figures, p_sources = [], [], []
    for x in entrees:
        if x.get("statut") not in ("gagnant", "perdant"):
            continue
        sig = sig_par_cle.get(x["cle"])
        if sig is None:
            continue
        ctx = (x.get("debat") or {}).get("ctx")
        if ctx:
            try:
                p_avocats.append((sig, Contexte(**ctx)))
            except Exception:
                pass
        if x.get("figures"):
            p_figures.append((sig, list(x["figures"])))
        srcs = (x.get("direction") or {}).get("sources")
        if srcs:
            p_sources.append((sig, [Source(s["code"], "?", s["sens"], 1.0, "")
                                    for s in srcs]))
    return p_avocats, p_figures, p_sources


def audits_courants(sig=None) -> dict:
    """Les audits que `cerveau.sante()` consomme — cache 300 s (la route
    /api/cerveau les relit à chaque affichage de page)."""
    if time.time() - _CACHE_AUDITS["t"] < 300 and _CACHE_AUDITS["audits"]:
        return _CACHE_AUDITS["audits"]
    from superviseur_apprenant import auditer_sl, courbe_calibration
    from gold_agent.apprentissage import signaux
    sig = sig if sig is not None else signaux()
    sl = [s for s in sig if s.statut == "SL"]
    indet = sum(1 for s in sl if auditer_sl(s).cause == "indetermine")
    inversee = None
    tranches = [t for t in courbe_calibration(sig) if t.get("n", 0) >= 20]
    if len(tranches) >= 2 and tranches[-1]["taux_reel"] < tranches[0]["taux_reel"]:
        inversee = (f"bande {tranches[-1]['tranche']} : "
                    f"{tranches[-1]['taux_reel']:.0%} réel contre "
                    f"{tranches[0]['taux_reel']:.0%} en {tranches[0]['tranche']}")
    _CACHE_AUDITS["audits"] = {"sl_indetermines": indet, "sl_total": len(sl),
                               "calibration_inversee": inversee}
    _CACHE_AUDITS["t"] = time.time()
    return _CACHE_AUDITS["audits"]


def cycle_complet(forcer: bool = False) -> str:
    """Un tour : calibrations → cerveau.cycle → sauver + rapport."""
    import avocats
    import cerveau
    import direction as dir_mod
    import figures as fig_mod
    import superviseur_apprenant as sup
    from gold_agent import journal
    from gold_agent.apprentissage import calibrage_actuel, signaux

    entrees = journal._charger()
    sig = signaux(entrees)
    sig_par_cle = {s.id: s for s in sig}
    p_avocats, p_figures, p_sources = _paires_depuis_journal(entrees, sig_par_cle)

    calibrations = {
        "agent": {k: v["poids"] for k, v in sup.poids_agents(sig).items()
                  if v.get("fiable")},
        "argument": {k: v.poids for k, v in avocats.calibrer(p_avocats).items()},
        "figure": {k: v.poids for k, v in fig_mod.calibrer(p_figures).items()},
        "source": {k: v.poids for k, v in dir_mod.calibrer(p_sources).items()},
    }

    etat = cerveau.cycle(sig, cerveau.charger(CERVEAU_JSON),
                         calibrations=calibrations, forcer=forcer)
    # le calibrage existant (couples COUPE, seuil mesuré) entre dans l'état
    cal = calibrage_actuel()
    etat.combos_coupes = [k for k, v in (cal.get("combos") or {}).items()
                          if v.get("verdict") == "COUPE"]
    s_cal = cal.get("seuil") or {}
    etat.seuil_emission = (s_cal.get("seuil")
                           if s_cal.get("rentable") else None)
    cerveau.sauver(etat, CERVEAU_JSON)

    problemes = cerveau.sante(etat, sig, audits_courants(sig))
    RAPPORT.write_text(cerveau.rapport(etat, problemes))
    _CACHE_AUDITS["live"] = None            # le bandeau relira l'état neuf
    return etat.motif_dernier_cycle


def etat_pour_le_site() -> dict:
    """GET /api/cerveau — l'état live du bandeau, cache 60 s."""
    if _CACHE_AUDITS["live"] is not None \
            and time.time() - _CACHE_AUDITS["t_live"] < 60:
        return _CACHE_AUDITS["live"]
    import cerveau
    etat = cerveau.charger(CERVEAU_JSON)
    try:
        from gold_agent.apprentissage import signaux
        sig = signaux()
    except Exception:
        sig = []
    live = cerveau.etat_live(etat, cerveau.sante(etat, sig, audits_courants(sig)))
    _CACHE_AUDITS["live"] = live
    _CACHE_AUDITS["t_live"] = time.time()
    return live


class EtapeCerveau:
    """Contrat boucles.Boucle : un tour horaire du cerveau."""

    def __call__(self) -> None:
        from datetime import datetime
        motif = cycle_complet()
        print(f"[{datetime.now():%H:%M:%S}] cerveau : {motif}", flush=True)


if __name__ == "__main__":
    print(cycle_complet(forcer="--forcer" in sys.argv))
