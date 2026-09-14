"""Donnees de navigation du site (SPEC_SITE_V3 §2-§4).

- grilles_instruments() : les 4 marches et leurs instruments avec un prix
  DIFFERE (cache yfinance de la constellation, recalcul 6 h). La grille
  l'affiche comme tel : un prix de la veille presente comme du direct fait
  entrer sur un niveau qui n'existe plus.
- signaux_actifs(resultats) : LA liste unique dont derivent, par calcul,
  toutes les pastilles (marche, instrument, timeframe) ET la notification
  telephone. Deux compteurs calcules separement finissent toujours par
  diverger.

Aucun appel reseau ici : tout vient du cache disque et du paquet.
"""
from __future__ import annotations

import time

from . import instruments


def grilles_instruments() -> dict:
    """{marche: [tuiles], "age_heures": x} — prix differes du cache."""
    fermetures, age_h = None, None
    try:
        from . import constellation_source
        px = constellation_source.prix()
        if px is not None:
            fermetures = px
            age_h = round((time.time() - constellation_source.CACHE.stat().st_mtime)
                          / 3600, 1)
    except Exception:
        pass

    out: dict = {"age_heures": age_h}
    for marche in instruments.MARCHES_ORDRE:
        tuiles = []
        for inst in instruments.par_marche(marche):
            prix = variation = None
            code_yf = inst.code_pour("yahoo")
            if fermetures is not None and code_yf in getattr(fermetures, "columns", []):
                serie = fermetures[code_yf].dropna()
                if len(serie) >= 2:
                    prix = round(float(serie.iloc[-1]), inst.decimales)
                    veille = float(serie.iloc[-2])
                    if veille:
                        variation = round((prix / veille - 1) * 100, 2)
            tuiles.append({"cle": inst.cle, "libelle": inst.symbole,  # noqa: E501
                           "nom": inst.nom, "marche": marche,
                           "tv": inst.code_pour("tv"),
                           "binance": (inst.code_pour("binance")
                                       if inst.code_pour("binance") != inst.symbole
                                       else None),
                           "decimales": inst.decimales,
                           "prix": prix, "variation_pct": variation})
        if marche in ("crypto", "actions"):
            # demande de Mushine : « ce qui bouge trop » en premier
            tuiles.sort(key=lambda t: -abs(t["variation_pct"] or 0))
        out[marche] = tuiles
    return out


def signaux_actifs(resultats: list, symbole: str) -> list[dict]:
    """La liste unique des signaux EMIS et encore actifs (non suspendus)."""
    inst = instruments.obtenir(symbole)
    out = []
    for r in resultats:
        st = r.get("setup") or {}
        if not st.get("setup") or st.get("suspendu"):
            continue
        out.append({"instrument": inst.cle, "libelle": inst.symbole,
                    "marche": inst.marche, "tf": r["nom"],
                    "sens": st["setup"], "entree": st.get("entree"),
                    "sl": st.get("stop"), "tp1": st.get("objectif"),
                    "rr": st.get("rr")})
    return out
