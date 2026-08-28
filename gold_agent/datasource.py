"""Sources de données externes — historique long et macro.

Le pont TradingView plafonne à 300 bougies, ce qui rend tout backtest
statistiquement vide. Ces sources fournissent des années d'historique.

Les clés sont lues depuis `.env` ou l'environnement. Elles ne transitent
jamais par la conversation : c'est toi qui écris le fichier.

Transport par `curl` plutôt que `urllib` : l'installation Python 3.14 de
cette machine n'a pas ses certificats CA (erreur CERTIFICATE_VERIFY_FAILED).
Passer par curl utilise les certificats système et évite de modifier ton
installation. La vérification TLS reste donc active — on ne la désactive pas.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ENV = RACINE / ".env"

# Compteur de requetes : le plan gratuit Twelve Data est plafonne a 800/jour.
# Sans suivi, on ne decouvre le depassement qu'au moment ou tout casse.
COMPTEUR = {"twelvedata": 0, "fred": 0, "depuis": None}

# --------------------------------------------------------------------------
# Rotation de cles Twelve Data
#
# Chaque cle a son propre quota (800/jour, 8/min sur le plan gratuit). En les
# alternant a chaque requete, la charge se repartit au lieu d'epuiser la
# premiere. Une cle qui renvoie une erreur de quota est mise au repos et la
# suivante prend le relais immediatement, sans faire echouer l'appel.
# --------------------------------------------------------------------------
import threading as _th
import time as _t

_ROTATION = {"index": 0, "usage": {}, "repos": {}, "verrou": _th.Lock()}
REPOS_APRES_ERREUR = 65        # secondes — la limite Twelve Data est par minute


def cles_twelvedata() -> list[str]:
    """Toutes les cles disponibles, dans l'ordre du fichier."""
    env = _charger_env()
    brut = os.environ.get("TWELVEDATA_API_KEYS") or env.get("TWELVEDATA_API_KEYS", "")
    cles = [c.strip() for c in brut.split(",") if c.strip() and c.strip() != "..."]
    if not cles:
        seule = os.environ.get("TWELVEDATA_API_KEY") or env.get("TWELVEDATA_API_KEY", "")
        if seule and seule != "...":
            cles = [seule]
    if not cles:
        raise RuntimeError(
            "Aucune cle Twelve Data. Copie .env.example en .env et renseigne "
            "TWELVEDATA_API_KEYS=cle1,cle2,cle3")
    return cles


def _cle_suivante(cles: list[str]) -> tuple[str, int]:
    """Prochaine cle disponible, en sautant celles au repos."""
    maintenant = _t.time()
    with _ROTATION["verrou"]:
        n = len(cles)
        for saut in range(n):
            i = (_ROTATION["index"] + saut) % n
            if _ROTATION["repos"].get(i, 0) <= maintenant:
                _ROTATION["index"] = (i + 1) % n
                _ROTATION["usage"][i] = _ROTATION["usage"].get(i, 0) + 1
                return cles[i], i
        # Toutes au repos : on prend celle qui se libere le plus tot
        i = min(range(n), key=lambda k: _ROTATION["repos"].get(k, 0))
        _ROTATION["index"] = (i + 1) % n
        _ROTATION["usage"][i] = _ROTATION["usage"].get(i, 0) + 1
        return cles[i], i


def _mettre_au_repos(i: int, secondes: int = REPOS_APRES_ERREUR) -> None:
    with _ROTATION["verrou"]:
        _ROTATION["repos"][i] = _t.time() + secondes


def etat_rotation() -> dict:
    """Usage par cle et disponibilite — pour le tableau de bord."""
    try:
        n = len(cles_twelvedata())
    except RuntimeError:
        return {"cles": 0}
    maintenant = _t.time()
    with _ROTATION["verrou"]:
        return {
            "cles": n,
            "usage": [_ROTATION["usage"].get(i, 0) for i in range(n)],
            "au_repos": [i for i in range(n) if _ROTATION["repos"].get(i, 0) > maintenant],
            "total": sum(_ROTATION["usage"].values()),
            "quota_theorique": n * 800,
        }


def _charger_env() -> dict:
    valeurs = {}
    if ENV.exists():
        for ligne in ENV.read_text().splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            k, v = ligne.split("=", 1)
            valeurs[k.strip()] = v.strip()
    return valeurs


def cle(nom: str) -> str:
    valeur = os.environ.get(nom) or _charger_env().get(nom, "")
    if not valeur or valeur == "...":
        raise RuntimeError(
            f"{nom} absente. Copie .env.example en .env et colle ta cle dedans.\n"
            f"  cp '{RACINE}/.env.example' '{RACINE}/.env'")
    return valeur


class ErreurTransitoire(RuntimeError):
    """Panne passagere cote serveur (502, 503, reponse vide, timeout).

    A distinguer d'une erreur de quota : changer de cle n'aide pas quand
    c'est le serveur qui est indisponible — cela epuiserait toutes les cles
    pour rien. On rejoue la meme cle apres une pause.
    """


def _get(url: str, timeout: int = 45) -> dict:
    p = subprocess.run(["curl", "-s", "-m", str(timeout), url],
                       capture_output=True, text=True, timeout=timeout + 10)
    sortie = p.stdout.strip()
    if not sortie:
        raise ErreurTransitoire(f"reponse vide (curl {p.returncode})")
    try:
        return json.loads(sortie)
    except json.JSONDecodeError:
        court = sortie[:120].replace("\n", " ")
        if any(m in sortie for m in ("502", "503", "504", "Bad Gateway",
                                     "Service Unavailable", "Timeout")):
            raise ErreurTransitoire(f"serveur indisponible : {court}")
        raise RuntimeError(f"reponse non-JSON : {court}")


def _get_avec_reprise(url: str, essais: int = 3, pause: float = 4.0) -> dict:
    """Rejoue la MEME requete sur erreur transitoire, avec pause croissante."""
    derniere = None
    for n in range(essais):
        try:
            return _get(url)
        except ErreurTransitoire as e:
            derniere = e
            if n < essais - 1:
                _t.sleep(pause * (n + 1))
    raise derniere


# --------------------------------------------------------------------------
# Twelve Data — historique de prix
# --------------------------------------------------------------------------

INTERVALLES = {"D": "1day", "240": "4h", "60": "1h", "30": "30min",
               "15": "15min", "5": "5min", "1": "1min"}


def twelvedata_bars(symbole: str = "XAU/USD", tf: str = "60",
                    nombre: int = 5000) -> list[dict]:
    """Bougies OHLCV au même format que le pont TradingView (ordre chronologique)."""
    import datetime as _d
    if COMPTEUR["depuis"] is None:
        COMPTEUR["depuis"] = _d.datetime.now(_d.timezone.utc)
    intervalle = INTERVALLES.get(tf, tf)
    base = (f"https://api.twelvedata.com/time_series?symbol={symbole}"
            f"&interval={intervalle}&outputsize={min(nombre, 5000)}&order=ASC")

    cles = cles_twelvedata()
    derniere_erreur = None
    # Un tour complet au maximum : si toutes les cles sont a bout, l'appel
    # echoue franchement plutot que de boucler.
    for _ in range(len(cles)):
        k, i = _cle_suivante(cles)
        COMPTEUR["twelvedata"] += 1
        try:
            d = _get_avec_reprise(f"{base}&apikey={k}")
        except ErreurTransitoire as e:
            # Panne serveur : inutile de bruler les autres cles, on abandonne
            # franchement. Le cache prendra le relais en amont.
            raise RuntimeError(f"Twelve Data indisponible : {e}") from None
        except Exception as e:
            derniere_erreur = str(e)
            continue

        if "values" in d:
            break

        msg = str(d.get("message", d))
        code = d.get("code")
        derniere_erreur = msg
        if code in (429, 432) or "credit" in msg.lower() or "limit" in msg.lower():
            _mettre_au_repos(i)
            continue
        # Erreur non liee au quota (symbole inconnu, intervalle invalide...) :
        # changer de cle n'y changerait rien.
        raise RuntimeError(f"Twelve Data : {msg}")
    else:
        raise RuntimeError(f"Twelve Data — toutes les cles epuisees : {derniere_erreur}")

    import datetime as _dt
    bars = []
    for v in d["values"]:
        horodatage = v["datetime"]
        fmt = "%Y-%m-%d %H:%M:%S" if " " in horodatage else "%Y-%m-%d"
        t = int(_dt.datetime.strptime(horodatage, fmt).replace(
            tzinfo=_dt.timezone.utc).timestamp())
        bars.append({
            "time": t,
            "open": float(v["open"]), "high": float(v["high"]),
            "low": float(v["low"]), "close": float(v["close"]),
            "volume": float(v.get("volume") or 0),
        })
    return bars


# --------------------------------------------------------------------------
# FRED — macro. DFII10 = rendement reel du 10 ans US (TIPS).
# C'est la variable qui explique le mieux l'or sur longue periode.
# --------------------------------------------------------------------------

SERIES = {
    "taux_reel_10a": "DFII10",
    "taux_reel_5a": "DFII5",
    "nominal_10a": "DGS10",
    "point_mort_inflation_10a": "T10YIE",
    "dollar_index": "DTWEXBGS",
}


# --------------------------------------------------------------------------
# Prix en direct et suivi de quota
# --------------------------------------------------------------------------

_QUOTE = {"valeur": None, "t": 0.0, "verrou": _th.Lock()}
_USAGE = {"valeur": None, "t": 0.0, "verrou": _th.Lock()}
TTL_QUOTE = 15      # secondes — le sondage du navigateur est a 10 s
# 1 rafraichissement d'usage = 1 requete PAR cle : a 5 min cela coutait
# 1440 requetes/jour a lui seul. 30 min suffisent pour une jauge.
TTL_USAGE = 1800


def _ttl_quote_adaptatif() -> int:
    """Ralentit le prix en direct quand le quota s'epuise.

    A 80 % de consommation, mieux vaut un prix de 60 s que plus de prix du
    tout a 100 %. La degradation est progressive et automatique.
    """
    with _USAGE["verrou"]:
        u = _USAGE["valeur"]
    if not u or not u.get("part_pct"):
        return TTL_QUOTE
    pct = u["part_pct"]
    if pct >= 95:
        return 300
    if pct >= 80:
        return 60
    return TTL_QUOTE


def quote_direct(symbole: str = "XAU/USD", ttl: int | None = None) -> dict:
    """Dernier prix traite. Une seule requete, bien moins couteuse qu'une serie.

    Les bougies servent a l'analyse et changent lentement ; le prix affiche
    doit coller au marche. Separer les deux permet d'allonger le cache des
    bougies tout en gardant un prix frais.
    """
    if ttl is None:
        ttl = _ttl_quote_adaptatif()
    with _QUOTE["verrou"]:
        if _QUOTE["valeur"] and (_t.time() - _QUOTE["t"]) < ttl:
            v = dict(_QUOTE["valeur"])
            v["age"] = int(_t.time() - _QUOTE["t"])
            return v

    cles = cles_twelvedata()
    derniere = None
    for _ in range(len(cles)):
        k, i = _cle_suivante(cles)
        COMPTEUR["twelvedata"] += 1
        try:
            d = _get_avec_reprise(f"https://api.twelvedata.com/quote?symbol={symbole}&apikey={k}",
                                  essais=2, pause=2.0)
        except ErreurTransitoire as e:
            derniere = str(e)
            break
        if "close" in d:
            v = {"prix": round(float(d["close"]), 2),
                 "cloture_precedente": float(d.get("previous_close") or 0) or None,
                 "variation_pct": float(d.get("percent_change") or 0),
                 "marche_ouvert": bool(d.get("is_market_open")),
                 "horodatage": d.get("timestamp"), "age": 0}
            with _QUOTE["verrou"]:
                _QUOTE["valeur"], _QUOTE["t"] = v, _t.time()
            return v
        msg = str(d.get("message", d))
        derniere = msg
        if d.get("code") in (429, 432) or "credit" in msg.lower() or "limit" in msg.lower():
            _mettre_au_repos(i)
            continue
        break

    # Echec : on rend la derniere valeur connue plutot que rien, en la datant
    with _QUOTE["verrou"]:
        if _QUOTE["valeur"]:
            v = dict(_QUOTE["valeur"])
            v["age"] = int(_t.time() - _QUOTE["t"])
            v["erreur"] = derniere
            return v
    raise RuntimeError(f"quote indisponible : {derniere}")


def usage_api(ttl: int = TTL_USAGE) -> dict:
    """Quota reellement consomme, interroge cle par cle chez Twelve Data.

    Le compteur interne ne voit que la session en cours ; cet endpoint donne
    la consommation reelle du jour, toutes sessions confondues.
    """
    with _USAGE["verrou"]:
        if _USAGE["valeur"] and (_t.time() - _USAGE["t"]) < ttl:
            v = dict(_USAGE["valeur"])
            v["age"] = int(_t.time() - _USAGE["t"])
            return v

    detail, total_utilise, total_limite = [], 0, 0
    for i, k in enumerate(cles_twelvedata()):
        COMPTEUR["twelvedata"] += 1
        try:
            d = _get_avec_reprise(f"https://api.twelvedata.com/api_usage?apikey={k}",
                                  essais=2, pause=2.0)
            utilise = int(d.get("daily_usage", 0))
            limite = int(d.get("plan_daily_limit", 800))
            detail.append({"cle": i + 1, "utilise": utilise, "limite": limite,
                           "restant": max(0, limite - utilise),
                           "par_minute": f"{d.get('current_usage','?')}/{d.get('plan_limit','?')}"})
            total_utilise += utilise
            total_limite += limite
        except Exception as e:
            detail.append({"cle": i + 1, "erreur": str(e)[:60]})

    v = {"detail": detail, "utilise": total_utilise, "limite": total_limite,
         "restant": max(0, total_limite - total_utilise),
         "part_pct": round(total_utilise / total_limite * 100, 1) if total_limite else None,
         "age": 0}
    with _USAGE["verrou"]:
        _USAGE["valeur"], _USAGE["t"] = v, _t.time()
    return v


def fred_serie(nom: str, debut: str = "2023-01-01") -> list[dict]:
    """Série FRED. `nom` accepte un alias de SERIES ou un identifiant brut."""
    sid = SERIES.get(nom, nom)
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
           f"&observation_start={debut}&file_type=json&api_key={cle('FRED_API_KEY')}")
    d = _get(url)
    if "observations" not in d:
        raise RuntimeError(f"FRED : {d.get('error_message', d)}")
    return [{"date": o["date"], "valeur": float(o["value"])}
            for o in d["observations"] if o["value"] not in (".", "")]


def disponible() -> dict:
    """Quelles sources sont utilisables ici et maintenant."""
    etat = {}
    try:
        etat["twelvedata"] = f"{len(cles_twelvedata())} cle(s)"
    except RuntimeError:
        etat["twelvedata"] = "cle absente"
    try:
        cle("FRED_API_KEY")
        etat["fred"] = "cle presente"
    except RuntimeError:
        etat["fred"] = "cle absente"
    return etat
