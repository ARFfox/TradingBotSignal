"""AG-05 Minieres & Flux : divergence or/minieres, positionnement COT,
saisonnalite. Separe de news.py (regle 17 : aucun fichier > 500 lignes) —
news.py garde le calendrier, la macro FRED et les actualites.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import threading
import time

from . import datasource as ds, instruments

_MINES = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
TTL_MINES = 4 * 3600


def minieres(fenetre: int = 20, ttl: int = TTL_MINES) -> dict:
    """Divergence or / minières sur `fenetre` jours ouvrés."""
    with _MINES["verrou"]:
        if _MINES["valeur"] is not None and (time.time() - _MINES["t"]) < ttl:
            return _MINES["valeur"]

    out = {"disponible": False, "arguments": []}
    try:
        aem = ds.twelvedata_bars("AEM", "D", fenetre + 10)
        oro = ds.twelvedata_bars(instruments.par_defaut().symbole, "D", fenetre + 10)
        pa = {dt.datetime.fromtimestamp(b["time"], dt.timezone.utc).date(): b["close"] for b in aem}
        po = {dt.datetime.fromtimestamp(b["time"], dt.timezone.utc).date(): b["close"] for b in oro}
        jours = sorted(set(pa) & set(po))[-fenetre:]
        if len(jours) < fenetre:
            raise RuntimeError(f"{len(jours)} jours communs seulement")

        var_aem = (pa[jours[-1]] / pa[jours[0]] - 1) * 100
        var_or = (po[jours[-1]] / po[jours[0]] - 1) * 100
        out = {
            "disponible": True,
            "fenetre_jours": fenetre,
            "aem": {"dernier": round(pa[jours[-1]], 2), "variation_pct": round(var_aem, 2)},
            "or": {"variation_pct": round(var_or, 2)},
            "arguments": [],
        }

        # Divergence : l'or bouge nettement, les minieres (qui amplifient
        # normalement x1,4) vont dans l'autre sens. Seuils : 2 % sur l'or
        # pour parler d'un mouvement, signe oppose sur AEM.
        if var_or >= 2.0 and var_aem <= 0:
            out["arguments"].append(("baissier", 1.5,
                f"divergence minières : or {var_or:+.1f}% sur {fenetre} j mais AEM {var_aem:+.1f}% — "
                f"les actionnaires des minières ne confirment pas la hausse"))
            out["divergence"] = "baissiere"
        elif var_or <= -2.0 and var_aem >= 0:
            out["arguments"].append(("haussier", 1.5,
                f"divergence minières : or {var_or:+.1f}% sur {fenetre} j mais AEM {var_aem:+.1f}% — "
                f"les minières ne confirment pas la baisse"))
            out["divergence"] = "haussiere"
        else:
            out["divergence"] = None
    except Exception as e:
        out["erreur"] = str(e)[:120]

    with _MINES["verrou"]:
        _MINES["valeur"], _MINES["t"] = out, time.time()
    return out


# --------------------------------------------------------------------------
# Positionnement COT (CFTC) : les positions REELLES des fonds speculatifs
# sur les contrats or COMEX, declarees chaque semaine. Pas des opinions
# d'analystes — des engagements chiffres.
#
# Lecture double, volontairement :
#   - la TENDANCE du positionnement net soutient le mouvement en cours ;
#   - un positionnement EXTREME (percentile eleve) est un trade encombre :
#     quand tout le monde est deja long, il ne reste plus d'acheteurs, et
#     les debouclages sont violents.
# --------------------------------------------------------------------------

URL_COT = ("https://publicreporting.cftc.gov/resource/6dca-aqww.json"
           "?$select=report_date_as_yyyy_mm_dd,noncomm_positions_long_all,"
           "noncomm_positions_short_all,open_interest_all"
           "&$where=starts_with(market_and_exchange_names,'GOLD%20-%20COMMODITY')"
           "&$order=report_date_as_yyyy_mm_dd%20DESC&$limit=156")

_COT = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
TTL_COT = 12 * 3600      # publication hebdomadaire — inutile de sonder plus


def positionnement(ttl: int = TTL_COT) -> dict:
    """Position nette des fonds spéculatifs sur l'or, percentile 3 ans."""
    with _COT["verrou"]:
        if _COT["valeur"] is not None and (time.time() - _COT["t"]) < ttl:
            return _COT["valeur"]

    out = {"disponible": False, "arguments": []}
    try:
        from .news import _curl_json
        brut = _curl_json(URL_COT)
        series = []
        for r in brut:
            net = (int(float(r["noncomm_positions_long_all"]))
                   - int(float(r["noncomm_positions_short_all"])))
            series.append({"date": r["report_date_as_yyyy_mm_dd"][:10], "net": net})
        if len(series) < 20:
            raise RuntimeError(f"{len(series)} rapports seulement")
        series.sort(key=lambda x: x["date"])

        nets = [x["net"] for x in series]
        actuel = nets[-1]
        percentile = sum(1 for v in nets if v < actuel) / len(nets) * 100
        var_4s = actuel - nets[-5] if len(nets) >= 5 else 0

        out = {
            "disponible": True,
            "date": series[-1]["date"],
            "net": actuel,
            "percentile": round(percentile, 0),
            "variation_4s": var_4s,
            "semaines": len(nets),
            "arguments": [],
        }

        # Tendance : plus de 15k contrats en 4 semaines est un mouvement franc
        if var_4s >= 15000:
            out["arguments"].append(("haussier", 1.5,
                f"fonds spéculatifs en accumulation : net {actuel:+,} contrats or, "
                f"{var_4s:+,} en 4 semaines (COT)"))
        elif var_4s <= -15000:
            out["arguments"].append(("baissier", 1.5,
                f"fonds spéculatifs en dégagement : net {actuel:+,} contrats or, "
                f"{var_4s:+,} en 4 semaines (COT)"))

        # Extreme : au-dela du 90e percentile, le camp long est plein
        if percentile >= 90:
            out["arguments"].append(("baissier", 2.0,
                f"positionnement long au {percentile:.0f}e percentile sur "
                f"{len(nets)} semaines — trade encombré, débouclages violents possibles"))
        elif percentile <= 10:
            out["arguments"].append(("haussier", 2.0,
                f"positionnement au {percentile:.0f}e percentile — camp vendeur plein, "
                f"rebond de couverture possible"))
    except Exception as e:
        out["erreur"] = str(e)[:120]

    with _COT["verrou"]:
        _COT["valeur"], _COT["t"] = out, time.time()
    return out


# --------------------------------------------------------------------------
# Actualites geopolitiques (Google News RSS, sans cle)
#
# Le calendrier economique ne voit que les evenements PROGRAMMES : un conflit
# arme n'y figure pas. Le 31/08/2026, le systeme a vendu dans un marche
# secoue par des frappes americaines sur l'Iran sans le savoir — 10 stops
# fauches. Cette couche scanne les titres recents et degrade la confiance
# du systeme quand le regime devient geopolitique.
# --------------------------------------------------------------------------

_SAISON = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
TTL_SAISON = 24 * 3600
FICHIER_SAISON = pathlib.Path.home() / ".gold_agent_saison.json"
NOMS_MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin",
             "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def saisonnalite(ttl: int = TTL_SAISON) -> dict:
    with _SAISON["verrou"]:
        if _SAISON["valeur"] is not None and (time.time() - _SAISON["t"]) < ttl:
            return _SAISON["valeur"]

    out = {"disponible": False, "arguments": []}
    try:
        if FICHIER_SAISON.exists() and time.time() - FICHIER_SAISON.stat().st_mtime < ttl:
            out = json.loads(FICHIER_SAISON.read_text())
        else:
            from collections import defaultdict
            bars = ds.twelvedata_bars(instruments.par_defaut().symbole, "D", 5000)
            debut, fin = {}, {}
            for b in bars:
                d = dt.datetime.fromtimestamp(b["time"], dt.timezone.utc)
                cle = (d.year, d.month)
                debut.setdefault(cle, b["close"])
                fin[cle] = b["close"]
            rend = defaultdict(list)
            for cle in debut:
                if debut[cle]:
                    rend[cle[1]].append((fin[cle] / debut[cle] - 1) * 100)
            mois = dt.datetime.now(dt.timezone.utc).month
            r = rend[mois]
            moyen = sum(r) / len(r)
            taux = sum(1 for x in r if x > 0) / len(r) * 100
            out = {"disponible": True, "mois": NOMS_MOIS[mois],
                   "annees": len(r), "moyen_pct": round(moyen, 2),
                   "taux_positif_pct": round(taux),
                   "tableau": {NOMS_MOIS[m]: {"moyen": round(sum(v)/len(v), 2),
                                              "positif": round(sum(1 for x in v if x > 0)/len(v)*100)}
                               for m, v in sorted(rend.items())},
                   "arguments": []}
            if moyen >= 1.0 and taux >= 60:
                out["arguments"].append(("haussier", 1.0,
                    f"saisonnalité : {NOMS_MOIS[mois]} historiquement favorable à l'or "
                    f"({moyen:+.1f}% en moyenne, {taux:.0f}% de mois positifs sur {len(r)} ans)"))
            elif moyen <= -0.3 and taux <= 45:
                out["arguments"].append(("baissier", 1.0,
                    f"saisonnalité : {NOMS_MOIS[mois]} historiquement défavorable à l'or "
                    f"({moyen:+.1f}%, {taux:.0f}% de mois positifs sur {len(r)} ans)"))
            FICHIER_SAISON.write_text(json.dumps(out, ensure_ascii=False))
    except Exception as e:
        out["erreur"] = str(e)[:100]

    with _SAISON["verrou"]:
        _SAISON["valeur"], _SAISON["t"] = out, time.time()
    return out


# --------------------------------------------------------------------------
# Flux crypto (AG-05) — funding, open interest, ratio long/short des gros
# comptes (Binance Futures, public, sans cle). L'equivalent crypto du COT,
# quotidien au lieu d'hebdomadaire — pertinent pour l'or depuis que la
# constellation MESURE le recouplage or/crypto (BTC +0,66 sur 30 j).
# LECTURE de positionnement, pas un vote : rien ici n'entre au consensus.
# --------------------------------------------------------------------------
_FLUX_CRYPTO = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
TTL_FLUX_CRYPTO = 900          # les donnees bougent a l'heure, pas a la seconde

FUNDING_CHARGE = 0.03          # %/8 h au-dela duquel les longs payent cher
RATIO_CHARGE = 1.5             # au-dela : positionnement long des gros comptes
RATIO_VENDEUR = 0.7


def flux_crypto(ttl: int = TTL_FLUX_CRYPTO, feed=None) -> dict:
    """{disponible, funding_pct, oi_var24h_pct, ratio_ls, part_long_pct,
    lecture: [...]} — `feed` injectable pour tester sans reseau."""
    with _FLUX_CRYPTO["verrou"]:
        if (feed is None and _FLUX_CRYPTO["valeur"] is not None
                and time.time() - _FLUX_CRYPTO["t"] < ttl):
            return _FLUX_CRYPTO["valeur"]

    out = {"disponible": False, "lecture": []}
    try:
        if feed is None:
            from feeds.binance import BinanceFutures
            feed = BinanceFutures()
        sym = instruments.par_marche("crypto")[0].code_pour("binance")
        fu = feed.funding(sym)
        oi = feed.open_interest(sym)
        rl = feed.ratio_long_short(sym)
        lecture = []
        if fu:
            if fu["taux_pct"] >= FUNDING_CHARGE:
                lecture.append(f"funding {fu['taux_pct']:+.3f} %/8 h : les longs "
                               f"payent cher — positionnement long chargé")
            elif fu["taux_pct"] <= -FUNDING_CHARGE:
                lecture.append(f"funding {fu['taux_pct']:+.3f} %/8 h : les shorts "
                               f"payent — positionnement vendeur chargé")
            else:
                lecture.append(f"funding {fu['taux_pct']:+.3f} %/8 h : neutre")
        if oi:
            sens_oi = "entre" if oi["variation_pct"] > 0 else "sort"
            lecture.append(f"open interest {oi['variation_pct']:+.1f} % sur "
                           f"{oi['heures']} h : l'argent {sens_oi}")
        if rl:
            if rl["ratio"] >= RATIO_CHARGE:
                lecture.append(f"gros comptes {rl['part_long_pct']} % longs "
                               f"(ratio {rl['ratio']}) — consensus acheteur chargé")
            elif rl["ratio"] <= RATIO_VENDEUR:
                lecture.append(f"gros comptes {rl['part_long_pct']} % longs "
                               f"(ratio {rl['ratio']}) — consensus vendeur chargé")
            else:
                lecture.append(f"gros comptes : ratio L/S {rl['ratio']} — équilibré")
        out = {"disponible": bool(fu or oi or rl), "symbole": sym,
               "funding_pct": (fu or {}).get("taux_pct"),
               "oi_var24h_pct": (oi or {}).get("variation_pct"),
               "ratio_ls": (rl or {}).get("ratio"),
               "part_long_pct": (rl or {}).get("part_long_pct"),
               "lecture": lecture}
    except Exception as e:
        out["erreur"] = str(e)[:80]
    if feed is None or out.get("disponible"):
        with _FLUX_CRYPTO["verrou"]:
            _FLUX_CRYPTO["valeur"], _FLUX_CRYPTO["t"] = out, time.time()
    return out
