"""Analyse des news : calendrier économique + macro FRED.

Deux couches distinctes, aux rôles différents :

1. CALENDRIER (ForexFactory, JSON public, sans clé) — le risque événementiel.
   Avant un chiffre à fort impact (NFP, CPI, FOMC), le spread s'élargit et le
   prix peut sauter plusieurs ATR en quelques secondes : les stops calculés
   n'ont plus de sens. L'agent doit s'abstenir AVANT, pas expliquer après.

2. MACRO (FRED, clé gratuite) — la direction de fond. Sur longue période,
   l'or suit d'abord les taux réels US (inversement) et le dollar. Ce sont
   des arguments de débat, pas des signaux d'exécution.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
import threading
import time

from . import datasource as ds

URL_CALENDRIER = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# L'or est cote en dollars : seuls les evenements USD le frappent directement.
# "All" couvre les evenements globaux (G20, guerres tarifaires...).
PAYS_SUIVIS = {"USD", "All"}

_CAL = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
_MACRO = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
TTL_CALENDRIER = 3600      # le calendrier de la semaine bouge peu
TTL_MACRO = 6 * 3600       # series quotidiennes


def _curl_json(url: str, timeout: int = 30):
    p = subprocess.run(["curl", "-s", "-m", str(timeout), url],
                       capture_output=True, text=True, timeout=timeout + 10)
    if not p.stdout.strip():
        raise RuntimeError("reponse vide")
    return json.loads(p.stdout)


# --------------------------------------------------------------------------
# Calendrier economique
# --------------------------------------------------------------------------

FICHIER_CAL = pathlib.Path.home() / ".gold_agent_calendrier.json"


def calendrier(ttl: int = TTL_CALENDRIER) -> list[dict]:
    """Événements USD de la semaine, horodatés en UTC.

    Cache sur DISQUE et pas seulement en mémoire : le feed ForexFactory
    limite les requêtes rapprochées, et chaque processus (analyse, tableau,
    surveillant) repartirait sinon de zéro. En cas de panne du feed, la
    dernière version connue est réutilisée — un calendrier d'hier vaut mieux
    que pas de calendrier : les événements de la semaine y figurent déjà.
    """
    with _CAL["verrou"]:
        if _CAL["valeur"] is not None and (time.time() - _CAL["t"]) < ttl:
            return _CAL["valeur"]

    if FICHIER_CAL.exists():
        age = time.time() - FICHIER_CAL.stat().st_mtime
        if age < ttl:
            try:
                evenements = json.loads(FICHIER_CAL.read_text())
                with _CAL["verrou"]:
                    _CAL["valeur"], _CAL["t"] = evenements, time.time()
                return evenements
            except Exception:
                pass

    try:
        brut = _curl_json(URL_CALENDRIER)
    except Exception:
        if FICHIER_CAL.exists():
            evenements = json.loads(FICHIER_CAL.read_text())
            with _CAL["verrou"]:
                _CAL["valeur"], _CAL["t"] = evenements, time.time()
            return evenements
        raise
    evenements = []
    for e in brut:
        if e.get("country") not in PAYS_SUIVIS:
            continue
        try:
            quand = dt.datetime.fromisoformat(e["date"]).astimezone(dt.timezone.utc)
        except (ValueError, KeyError):
            continue
        evenements.append({
            "quand_utc": quand.isoformat(timespec="minutes"),
            "timestamp": int(quand.timestamp()),
            "titre": e.get("title", "?"),
            "impact": e.get("impact", "?"),
            "prevu": e.get("forecast") or None,
            "precedent": e.get("previous") or None,
        })
    evenements.sort(key=lambda x: x["timestamp"])

    try:
        FICHIER_CAL.write_text(json.dumps(evenements, ensure_ascii=False))
    except Exception:
        pass
    with _CAL["verrou"]:
        _CAL["valeur"], _CAL["t"] = evenements, time.time()
    return evenements


def prochains(fenetre_heures: float = 24.0, impact_min: str = "High") -> list[dict]:
    """Événements à venir dans la fenêtre, du plus proche au plus lointain."""
    rangs = {"Low": 0, "Medium": 1, "High": 2}
    seuil = rangs.get(impact_min, 2)
    maintenant = time.time()
    horizon = maintenant + fenetre_heures * 3600
    out = []
    for e in calendrier():
        if e["timestamp"] < maintenant - 1800:      # passe depuis plus de 30 min
            continue
        if e["timestamp"] > horizon:
            break
        if rangs.get(e["impact"], 0) < seuil:
            continue
        d = dict(e)
        d["dans_minutes"] = round((e["timestamp"] - maintenant) / 60)
        out.append(d)
    return out


def risque_evenementiel() -> dict:
    """Verdict pour le garde-fou : peut-on raisonnablement entrer maintenant ?

    Fenêtres asymétriques à dessein : le danger est maximal juste AVANT et
    pendant la publication (le chiffre est inconnu), moindre après (le marché
    digère, mais la volatilité reste élevée ~30 min).
    """
    try:
        imminents = prochains(fenetre_heures=2.0, impact_min="High")
    except Exception as e:
        return {"etat": "inconnu", "detail": f"calendrier indisponible ({str(e)[:60]})",
                "evenements": []}

    en_cours = [e for e in imminents if -30 <= e["dans_minutes"] <= 5]
    tres_proches = [e for e in imminents if 5 < e["dans_minutes"] <= 60]
    proches = [e for e in imminents if 60 < e["dans_minutes"] <= 120]

    if en_cours:
        return {"etat": "veto", "evenements": en_cours,
                "detail": f"publication en cours ou imminente : {en_cours[0]['titre']}"}
    if tres_proches:
        e = tres_proches[0]
        return {"etat": "veto", "evenements": tres_proches,
                "detail": f"{e['titre']} dans {e['dans_minutes']} min — spread élargi, "
                          f"stops sans valeur pendant la publication"}
    if proches:
        e = proches[0]
        return {"etat": "reserve", "evenements": proches,
                "detail": f"{e['titre']} dans {round(e['dans_minutes']/60,1)} h — "
                          f"éviter les positions qui ne seraient pas gérées d'ici là"}
    return {"etat": "ok", "evenements": [], "detail": "aucun événement USD à fort impact sous 2 h"}


# --------------------------------------------------------------------------
# Macro FRED : taux reels et dollar
# --------------------------------------------------------------------------

def _tendance(serie: list[dict], jours: int) -> dict | None:
    """Variation sur N observations ouvrées (approximation de N jours)."""
    if len(serie) < jours + 1:
        return None
    a, b = serie[-jours - 1]["valeur"], serie[-1]["valeur"]
    return {"de": a, "vers": b, "variation": round(b - a, 3)}


def macro(ttl: int = TTL_MACRO) -> dict:
    """Lecture macro : taux réels 10 ans et dollar pondéré, avec leur pente."""
    with _MACRO["verrou"]:
        if _MACRO["valeur"] is not None and (time.time() - _MACRO["t"]) < ttl:
            return _MACRO["valeur"]

    out = {"disponible": False, "arguments": []}
    try:
        debut = (dt.date.today() - dt.timedelta(days=120)).isoformat()
        reels = ds.fred_serie("taux_reel_10a", debut=debut)
        dollar = ds.fred_serie("dollar_index", debut=debut)

        t20 = _tendance(reels, 20)          # ~1 mois ouvre
        d20 = _tendance(dollar, 20)
        out = {
            "disponible": True,
            "taux_reel_10a": {"dernier": reels[-1]["valeur"], "date": reels[-1]["date"],
                              "tendance_1m": t20},
            "dollar_large": {"dernier": dollar[-1]["valeur"], "date": dollar[-1]["date"],
                             "tendance_1m": d20},
            "arguments": [],
        }

        # Traduction en arguments de debat. Seuils : un dixieme de point de
        # taux reel sur un mois est un mouvement notable ; en dessous, bruit.
        if t20:
            if t20["variation"] >= 0.10:
                out["arguments"].append(("baissier", 2.5,
                    f"taux réels 10 ans en hausse ({t20['de']:.2f}% → {t20['vers']:.2f}% sur 1 mois) — "
                    f"vent contraire structurel pour l'or"))
            elif t20["variation"] <= -0.10:
                out["arguments"].append(("haussier", 2.5,
                    f"taux réels 10 ans en baisse ({t20['de']:.2f}% → {t20['vers']:.2f}% sur 1 mois) — "
                    f"soutien structurel pour l'or"))
        if d20:
            pct = d20["variation"] / d20["de"] * 100 if d20["de"] else 0
            if pct >= 1.0:
                out["arguments"].append(("baissier", 1.5,
                    f"dollar pondéré en hausse de {pct:+.1f}% sur 1 mois"))
            elif pct <= -1.0:
                out["arguments"].append(("haussier", 1.5,
                    f"dollar pondéré en baisse de {pct:+.1f}% sur 1 mois"))
    except Exception as e:
        out["erreur"] = str(e)[:120]

    with _MACRO["verrou"]:
        _MACRO["valeur"], _MACRO["t"] = out, time.time()
    return out


# --------------------------------------------------------------------------
# Minieres d'or (AEM) : confirmation, pas prediction
#
# Mesure sur 359 jours communs (03/2025-08/2026) : correlation quotidienne
# +0,80 mais correlations decalees toutes < 0,12 — AEM et l'or bougent
# ENSEMBLE, aucun des deux ne precede l'autre. La seule lecture defendable
# est la divergence de confirmation : l'or monte mais les minieres (beta
# ~1,4) refusent de suivre -> le mouvement manque d'adhesion.
# --------------------------------------------------------------------------

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
        oro = ds.twelvedata_bars("XAU/USD", "D", fenetre + 10)
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

URL_ACTUS = ("https://news.google.com/rss/search?"
             "q=gold+price+iran+OR+war+OR+strike+OR+attack+OR+conflict+when:2d"
             "&hl=en-US&gl=US&ceid=US:en")
FICHIER_ACTUS = pathlib.Path.home() / ".gold_agent_actus.json"
MOTS_CHAUDS = ("war", "strike", "strikes", "attack", "missile", "escalat",
               "conflict", "iran", "military", "retaliat", "sanctions")

_ACTUS = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
TTL_ACTUS = 900     # 15 min


def actualites(ttl: int = TTL_ACTUS) -> dict:
    """Titres récents liés à l'or + niveau de risque géopolitique.

    Le niveau est un COMPTAGE de mots-clés dans des titres de presse — un
    thermomètre grossier mais suffisant pour dire « le régime n'est plus
    technique ». Il ne prédit aucune direction : le 31/08, l'or a BAISSÉ
    sur les frappes (anticipations de hausse des taux), à rebours du
    réflexe « valeur refuge ».
    """
    import re
    with _ACTUS["verrou"]:
        if _ACTUS["valeur"] is not None and (time.time() - _ACTUS["t"]) < ttl:
            return _ACTUS["valeur"]

    out = {"disponible": False, "titres": [], "niveau": "inconnu"}
    try:
        p = subprocess.run(["curl", "-s", "-m", "25", URL_ACTUS],
                           capture_output=True, text=True, timeout=35)
        items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<pubDate>(.*?)</pubDate>",
                           p.stdout, re.S)
        if not items:
            raise RuntimeError("flux vide")
        titres = []
        chauds = 0
        for t, d in items[:25]:
            t = (t.replace("&amp;", "&").replace("&#39;", "'")
                 .replace("&quot;", '"').strip())
            touche = any(m in t.lower() for m in MOTS_CHAUDS)
            chauds += touche
            titres.append({"titre": t[:140], "date": d[5:16], "geopolitique": touche})
        part = chauds / len(titres)
        niveau = "eleve" if part >= 0.4 else ("modere" if part >= 0.15 else "calme")
        out = {"disponible": True, "titres": titres[:12], "niveau": niveau,
               "part_geopolitique_pct": round(part * 100),
               "note": ("regime geopolitique : les stops techniques sont peu fiables, "
                        "la direction ne suit pas forcement le reflexe valeur refuge")
               if niveau == "eleve" else None}
        FICHIER_ACTUS.write_text(json.dumps(out, ensure_ascii=False))
    except Exception as e:
        if FICHIER_ACTUS.exists():
            out = json.loads(FICHIER_ACTUS.read_text())
            out["age_note"] = f"flux indisponible ({str(e)[:50]}) — derniere version connue"
        else:
            out["erreur"] = str(e)[:100]

    with _ACTUS["verrou"]:
        _ACTUS["valeur"], _ACTUS["t"] = out, time.time()
    return out
