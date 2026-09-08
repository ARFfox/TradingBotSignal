"""Prix quotidiens pour la constellation. Cache disque, recalcul 6 h.

Volontairement séparé de datasource.py : Twelve Data est limité à
800 requêtes/jour et sert au temps réel sur XAU/USD. Ici il faut ~36 actifs
d'historique quotidien, ce que yfinance fournit gratuitement et sans clé.

Contrat (INTEGRATION_AG09.md, étape 1) :
- `prix()` retourne le cache immédiatement s'il a moins de 6 h ;
- cache périmé : le téléchargement part dans un THREAD, l'ancien cache est
  rendu tout de suite avec `attrs["perime"] = True` — la page ne bloque
  jamais ;
- aucun cache (premier lancement) : retourne None, le téléchargement
  démarre en fond, les cartes s'affichent en INITIALISATION ;
- yfinance absent ou réseau coupé : dernier cache marqué périmé, jamais
  d'exception qui remonte à la page.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

CACHE = Path.home() / ".constellation_prix.parquet"
FRAICHEUR_S = 6 * 3600
_TELECHARGEMENT = {"en_cours": False, "verrou": threading.Lock()}


def _univers() -> list[str]:
    """Union des tickers de la constellation (AG-09) et des 4 marches
    (AG-11..14) : une seule requete yfinance, un seul cache, deux
    consommateurs — c'est la contrainte d'INTEGRATION_MARCHES.md §2."""
    import sys
    racine = str(Path(__file__).resolve().parent.parent)
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from constellation_agent import NOMS
    tickers = set(NOMS)
    try:
        from agents_marches import MARCHES
        for m in MARCHES.values():
            tickers |= set(m["tickers"])
    except Exception:
        pass          # les marches sont optionnels, la constellation jamais
    return sorted(tickers)


def _telecharger() -> None:
    """Tâche de fond : 36 actifs × 3 ans de daily, puis écriture atomique."""
    try:
        import warnings
        warnings.filterwarnings("ignore")
        import yfinance as yf
        df = yf.download(_univers(), period="3y", interval="1d",
                         progress=False, auto_adjust=True)["Close"]
        if df is not None and len(df) > 100:
            tmp = CACHE.with_suffix(".tmp.parquet")
            df.to_parquet(tmp)
            tmp.replace(CACHE)
    except Exception:
        pass    # le dernier cache reste en place ; la page vit sa vie
    finally:
        with _TELECHARGEMENT["verrou"]:
            _TELECHARGEMENT["en_cours"] = False


def _lancer_telechargement() -> None:
    with _TELECHARGEMENT["verrou"]:
        if _TELECHARGEMENT["en_cours"]:
            return
        _TELECHARGEMENT["en_cours"] = True
    threading.Thread(target=_telecharger, daemon=True).start()


def prix(force: bool = False):
    """DataFrame de clôtures quotidiennes (colonnes = tickers), ou None."""
    import pandas as pd

    if CACHE.exists():
        age = time.time() - CACHE.stat().st_mtime
        try:
            df = pd.read_parquet(CACHE)
        except Exception:
            df = None
        if df is not None:
            if age >= FRAICHEUR_S or force:
                df.attrs["perime"] = True
                _lancer_telechargement()
            else:
                df.attrs["perime"] = False
            return df

    # Aucun cache lisible : on amorce en fond, la page affiche INITIALISATION
    _lancer_telechargement()
    return None
