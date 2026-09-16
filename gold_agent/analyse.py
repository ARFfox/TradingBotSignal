"""L'analyse d'UN timeframe — la fonction unique, pour tous les instruments.

Extraite de collecter() (SPEC_SITE_V3 niveau 3) : la meme analyse tourne
sur l'or (Twelve Data, comme avant, comportement identique) et, a la
demande, sur n'importe quel instrument du registre via les feeds
(Binance pour la crypto, Yahoo pour le reste). Deux copies de cette
logique divergeraient un jour sans que personne ne le voie — il n'y en a
qu'une.

REGLE D'EMISSION (regles 2-3 du SYSTEME) : l'analyse d'un instrument non
valide par le walk-forward s'affiche SUSPENDUE avec ce motif. Elle ne
journalise rien, ne notifie rien — c'est de la lecture, pas un signal.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import ict, indicators as ind, instruments, patterns as pat, \
    regime as rg, strategy as sg


def analyser_tf(bars: list[dict], spec: dict, fiabilite: dict,
                prix_direct: float | None = None,
                chrono: dict | None = None,
                cout_pts: float = 0.3,
                decimales: int = 2) -> dict:
    """Le coeur : indicateurs, setup, ICT, ABC, jauge — pour UN timeframe.

    `chrono` (optionnel) recoit les temps par agent, comme dans collecter.
    Ne leve jamais pour ICT/ABC (repli None) ; laisse remonter une erreur
    de donnees — l'appelant decide du repli.
    """
    t0 = time.perf_counter()
    _chr = chrono if chrono is not None else {}
    entree = {"nom": spec["nom"], "role": spec["role"], "tf": spec["tf"],
              "fiabilite": fiabilite}

    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    o = [b["open"] for b in bars]
    p = sg.Params(k_stop=spec.get("k_stop", 1.0), rr_min=1.5,
                  cout_pts=cout_pts, facteur_superieur=spec["mtf"],
                  decimales=decimales, **spec["params"])
    d0 = time.perf_counter()
    entree["setup"] = sg.setup_actuel(bars, p)
    _chr["stratege"] = _chr.get("stratege", 0.0) + (time.perf_counter() - d0)
    entree["prix"] = round(c[-1], 2)
    entree["prix_direct"] = prix_direct
    entree["rsi"] = ind.last_valid(ind.rsi(c, 14))
    entree["atr"] = ind.last_valid(ind.atr(h, l, c, 14))
    entree["ema_fast"] = ind.last_valid(ind.ema(c, p.ema_fast))
    entree["ema_slow"] = ind.last_valid(ind.ema(c, p.ema_slow))
    entree["periodes"] = [p.ema_fast, p.ema_slow]
    entree["extension"] = rg.score_extension(c[-1], entree["ema_fast"], entree["rsi"])
    _chr["structure"] = _chr.get("structure", 0.0) + (time.perf_counter() - t0)
    entree["volatilite"] = rg.regime_volatilite(h, l, c)
    entree["renversement"] = rg.renversement(o, h, l, c)
    d0 = time.perf_counter()
    try:
        entree["ict"] = ict.analyse_ict(bars, entree["atr"])
    except Exception:
        entree["ict"] = None
    try:
        zz = pat.zigzag(h, l, seuil=(entree["atr"] or 1) * 2)
        entree["abc"] = pat.correction_abc(zz, entree["atr"])
    except Exception:
        entree["abc"] = {"scenario": None}
    _chr["traceur"] = _chr.get("traceur", 0.0) + (time.perf_counter() - d0)

    # Pourcentage haussier de CE timeframe (jauge de la carte)
    b_pts = s_pts = 0.0
    if entree["ema_fast"] and entree["ema_slow"]:
        (b_pts, s_pts) = ((b_pts + 1.5, s_pts) if entree["ema_fast"] > entree["ema_slow"]
                          else (b_pts, s_pts + 1.5))
        if c[-1] > entree["ema_slow"]:
            b_pts += 1.0
        else:
            s_pts += 1.0
    if entree["rsi"] is not None:
        if entree["rsi"] >= 55:
            b_pts += 0.5
        elif entree["rsi"] <= 45:
            s_pts += 0.5
    tot = b_pts + s_pts
    entree["pct_haussier"] = round(b_pts / tot * 100) if tot else 50

    entree["bougies"] = [{"t": b["time"], "o": b["open"], "h": b["high"],
                          "l": b["low"], "c": b["close"]} for b in bars[-120:]]
    entree["erreur"] = None
    return entree


# --------------------------------------------------------------------------
# Analyse a la demande d'un instrument du registre (hors or)
# --------------------------------------------------------------------------
def bars_instrument(inst, tf_code: str, nombre: int = 600) -> list[dict]:
    """Bougies via l'adapter du registre : Binance (crypto), Yahoo sinon.
    L'or ne passe PAS ici — il garde son chemin Twelve Data historique."""
    if inst.code_pour("binance") != inst.symbole:
        # CHANTIER #10 : CCXT en premier (pagination et limites gérées par
        # une bibliothèque maintenue), l'adaptateur maison en repli — le
        # remplacement reste réversible par construction.
        try:
            from feeds.ccxt_feed import CcxtFeed
            bars = CcxtFeed().bars(inst.code_pour("binance"), tf_code, nombre)
            if bars:
                return bars
        except Exception:
            pass
        from feeds.binance import Binance
        return Binance().bars(inst.code_pour("binance"), tf_code, nombre)
    from feeds.yahoo import Yahoo
    return Yahoo().bars(inst.code_pour("yahoo"), tf_code, nombre)


def _verdict_walkforward(symbole: str, nom_tf: str) -> dict | None:
    try:
        chemin = Path(__file__).resolve().parent.parent / "research" / "verdicts.json"
        return (json.loads(chemin.read_text()).get(symbole) or {}).get(nom_tf)
    except Exception:
        return None


def analyse_instrument(cle: str, bougies: int = 600,
                       bars_par_tf: dict | None = None) -> dict:
    """L'analyse 5 TF d'un instrument NON emetteur, a la demande.

    - fiabilite = le verdict walk-forward reel quand il existe, sinon
      « non mesuré » ;
    - tout setup detecte est SUSPENDU (motif : instrument non valide) —
      rien n'entre au journal, rien ne notifie ;
    - `bars_par_tf` permet d'injecter des bougies (tests sans reseau).
    """
    from .tableau import TIMEFRAMES

    inst = instruments.par_cle(cle)
    if inst is None:
        raise KeyError(f"instrument inconnu : {cle}")
    if inst.symbole == instruments.par_defaut().symbole:
        raise ValueError("l'or passe par collecter(), pas par l'analyse a la demande")

    est_crypto = inst.code_pour("binance") != inst.symbole
    resultats = []
    for spec in TIMEFRAMES:
        if spec["nom"] == "H4" and not est_crypto:
            continue    # Yahoo n'a pas de 4 h natif — pas de donnees mensongeres
        v = _verdict_walkforward(inst.symbole, spec["nom"])
        if v:
            etat = "autorisé" if v.get("autorise") else "REFUSÉ"
            fiab = {"niveau": f"walk-forward {etat}",
                    "trades": v.get("trades"),
                    "esperance": v.get("r_moyen"), "pf": v.get("profit_factor"),
                    "creux": v.get("pire_creux"),
                    "note": f"{v.get('trades')} trades · R moyen "
                            f"{v.get('r_moyen'):+.3f} · PF {v.get('profit_factor')}"}
        else:
            fiab = {"niveau": "non mesuré",
                    "note": "aucun walk-forward encore — lancer "
                            "python3 -m research.rapport_edge"}
        try:
            bars = (bars_par_tf or {}).get(spec["nom"]) \
                or bars_instrument(inst, spec["tf"], bougies)
            if len(bars) < 120:
                raise RuntimeError(f"{len(bars)} bougies seulement")
            cout = (bars[-1]["close"] * inst.cout_pct / 100) if bars else 0.0
            entree = analyser_tf(bars, spec, fiab, cout_pts=cout,
                                 decimales=inst.decimales)
            st = entree.get("setup") or {}
            if st.get("setup"):
                if v and v.get("autorise"):
                    st["suspendu"] = ("émission multi-actifs non câblée — "
                                      "analyse seulement (validation à venir)")
                else:
                    st["suspendu"] = ("instrument non validé par le walk-forward "
                                      "— analyse seulement, aucune émission")
            entree["emission"] = False
        except Exception as e:
            entree = {"nom": spec["nom"], "role": spec["role"], "tf": spec["tf"],
                      "fiabilite": fiab, "erreur": str(e)[:120],
                      "setup": {"setup": None, "raison": "données indisponibles"},
                      "emission": False}
        resultats.append(entree)

    return {"symbole": inst.symbole, "cle": inst.cle, "nom": inst.nom,
            "marche": inst.marche, "timeframes": resultats,
            "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())}
