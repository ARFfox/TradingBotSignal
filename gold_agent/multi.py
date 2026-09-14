"""Multi-marches — les agents travaillent sur TOUT le site (demande de
Mushine, 15/09) : forex, matieres, crypto, actions.

Chaque tour de boucle :
1. prend la CRYPTO entiere (Binance, genereux et gratuit) + une TRANCHE
   des instruments Yahoo (rotation — yfinance n'aime pas les rafales) ;
2. analyse chaque instrument avec LA meme fonction que l'or
   (analyse.analyser_tf), note chaque setup avec LA meme decision du
   Superviseur (fiabilite = verdict walk-forward de CE couple, journal
   90 j de CE couple, poids Brier) ;
3. journalise (champ instrument), resout les signaux en cours avec les
   bougies fraiches, et notifie si la note passe le seuil de proprete.

C'est la grosse data d'apprentissage voulue : chaque resolution, sur
chaque instrument, rend le Superviseur plus severe sur ce qui perd et
plus genereux sur ce qui gagne — automatiquement, par couple
(instrument x timeframe). L'or garde son circuit Twelve Data intact.
"""
from __future__ import annotations

import threading
import time

TRANCHE_YAHOO = 8          # instruments Yahoo analyses par tour (rotation)
BARS = 320                 # assez pour EMA200 + pivots, leger pour l'API
_ETAT = {"index_yahoo": 0, "verrou": threading.Lock(),
         "signaux_actifs": [], "derniere_passe": {}}


def _plan_tour() -> list:
    """Crypto complete + tranche Yahoo du moment. Jamais l'or (il a son
    propre circuit temps reel)."""
    from . import instruments
    defaut = instruments.par_defaut().symbole
    crypto, yahoo = [], []
    for inst in instruments.REGISTRE.values():
        if inst.symbole == defaut:
            continue
        (crypto if inst.code_pour("binance") != inst.symbole else yahoo).append(inst)
    with _ETAT["verrou"]:
        i = _ETAT["index_yahoo"]
        _ETAT["index_yahoo"] = (i + TRANCHE_YAHOO) % max(1, len(yahoo))
    tranche = (yahoo + yahoo)[i:i + TRANCHE_YAHOO]
    return crypto + tranche


def analyser_et_emettre(inst, notifier=None) -> list[dict]:
    """Analyse un instrument, note, journalise, resout, notifie.
    Retourne les setups actifs (pour les pastilles)."""
    from . import analyse, avis as avis_agents, decision, journal, tableau
    from research import livetest

    est_crypto = inst.code_pour("binance") != inst.symbole
    try:
        sig_journal = journal._charger()
    except Exception:
        sig_journal = []
    try:
        from .tableau import DERNIER_PAQUET as _dp
    except Exception:
        _dp = None
    calibration = (_dp or {}).get("calibration") if isinstance(_dp, dict) else None

    actifs, bars_par_tf = [], {}
    for spec in tableau.TIMEFRAMES:
        if spec["nom"] == "H4" and not est_crypto:
            continue                      # pas de 4 h mensonger via Yahoo
        v = analyse._verdict_walkforward(inst.symbole, spec["nom"])
        if v:
            niveau = f"walk-forward {'autorisé' if v.get('autorise') else 'REFUSÉ'}"
            fiab = {"niveau": niveau, "note": f"{v.get('trades')} trades · "
                    f"R moyen {v.get('r_moyen'):+.3f} · PF {v.get('profit_factor')}"}
        else:
            fiab = {"niveau": "non mesuré",
                    "note": "walk-forward pas encore lancé sur ce couple"}
        try:
            bars = analyse.bars_instrument(inst, spec["tf"], BARS)
            if len(bars) < 120:
                continue
            bars_par_tf[spec["nom"]] = bars
            r = analyse.analyser_tf(bars, spec, fiab, cout_pts=0.0)
        except Exception:
            continue
        st = r.get("setup") or {}
        if not st.get("setup"):
            continue
        carreau = livetest.carreau(sig_journal, spec["nom"],
                                   instrument=inst.symbole)
        try:
            st["avis"] = avis_agents.directions(_dp or {}, r)
        except Exception:
            st["avis"] = {}
        st["decision_chef"] = decision.noter(
            st, fiab, None, False, None,
            carreau=carreau, calibration=calibration)
        nouveau = journal.enregistrer(spec["nom"], st, r.get("prix") or 0,
                                      fiab["niveau"], instrument=inst.symbole)
        actifs.append({"instrument": inst.cle, "libelle": inst.symbole,
                       "marche": inst.marche, "tf": spec["nom"],
                       "sens": st["setup"], "entree": st.get("entree"),
                       "sl": st.get("stop"), "tp1": st.get("objectif"),
                       "rr": st.get("rr"),
                       "note": st["decision_chef"]["pct"]})
        if nouveau and notifier and st["decision_chef"]["notifiable"]:
            notifier(inst, spec["nom"], st, r.get("prix"))

    # resolution des signaux en cours de CET instrument, bougies fraiches
    try:
        from . import journal as _j
        _j.resoudre(bars_par_tf, instrument=inst.symbole)
    except Exception:
        pass
    return actifs


class EtapeMulti:
    """Un TOUR de la boucle multi-marches (contrat boucles.Boucle)."""

    def __call__(self) -> None:
        from datetime import datetime
        from . import notify

        def _notifier(inst, tf, st, prix):
            dc = st.get("decision_chef") or {}
            fi = f"{(dc.get('pct'))}% Superviseur · {inst.marche}"
            try:
                notify.diffuser(f"{inst.symbole} {tf}", st, prix, fi, svg=None)
                print(f"[{datetime.now():%H:%M:%S}] multi {inst.symbole} {tf} "
                      f"{st['setup']} note {dc.get('pct')}% -> notifie", flush=True)
            except Exception:
                pass

        tous = []
        for inst in _plan_tour():
            try:
                tous.extend(analyser_et_emettre(inst, notifier=_notifier))
            except Exception:
                continue
        with _ETAT["verrou"]:
            # les signaux de la passe remplacent ceux de la meme famille ;
            # les instruments non repasses gardent leur derniere lecture 2 h
            maintenant = time.time()
            passe = _ETAT["derniere_passe"]
            for s in tous:
                passe[f"{s['instrument']}|{s['tf']}"] = {**s, "_t": maintenant}
            _ETAT["signaux_actifs"] = [
                {k: v for k, v in x.items() if k != "_t"}
                for x in passe.values() if maintenant - x["_t"] < 7200]
            _ETAT["derniere_passe"] = {
                k: x for k, x in passe.items() if maintenant - x["_t"] < 7200}


def signaux_actifs_multi() -> list[dict]:
    """Les signaux multi-marches du moment — pour les pastilles du site."""
    with _ETAT["verrou"]:
        return list(_ETAT["signaux_actifs"])
