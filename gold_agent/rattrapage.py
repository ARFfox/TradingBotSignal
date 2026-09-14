"""AG-17 Rattrapage — la divergence de convergence (SPEC_V2 §2B).

Quand deux actifs correles de facon STABLE divergent, l'ecart se referme
statistiquement. C'est une famille de setups que le systeme mono-actif ne
pouvait pas voir, et elle est peu correlee aux setups techniques — donc
elle diversifie vraiment.

Les deux garde-fous de la spec, sans lesquels c'est un piege :
1. UNIQUEMENT des paires a correlation STABLE (corr >= 0,70 ET stabilite
   >= 0,75). Sur une correlation instable, l'ecart ne se referme pas —
   il s'elargit.
2. Verifier qu'il n'y a pas de cause specifique : l'agent Vigie valide.
   Ici : toute opportunite nait marquee « a valider » si le risque
   evenementiel n'est pas calme.

Et une exigence du projet : le taux de fermeture historique est MESURE
sur les donnees de la paire (« cet ecart s'est referme sous N jours dans
X % des cas, sur K occurrences »), jamais affirme. Une paire sans
historique d'occurrences ne propose rien.

Module pur : on lui injecte les prix quotidiens. AUCUNE emission : ces
opportunites s'affichent, elles ne signalent pas (pas de walk-forward
passe = pas de signal, regle 2).
"""
from __future__ import annotations

CORR_MIN = 0.70          # seuil de confirmation (ANALYSE_CONSTELLATION §6)
STABILITE_MIN = 0.75     # la spec : « score >= 0,75 » — sinon piege
FENETRE_PERF = 5         # jours de l'ecart de performance
FENETRE_SIGMA = 120      # jours pour normaliser l'ecart
SEUIL_Z = 1.8            # au-dela : divergence
Z_FERME = 0.5            # en-deca : l'ecart est considere referme
HORIZON_J = 6            # delai de fermeture mesure
OCCURRENCES_MIN = 8      # sous ce nombre, la statistique ne dit rien


def _ecarts_normalises(pa, pb):
    """Serie z de l'ecart de performance 5 j entre deux series de prix
    alignees (pandas). z = (perf5(a) - perf5(b)) / sigma_120(ecarts)."""
    import numpy as np
    ra = np.log(pa / pa.shift(FENETRE_PERF))
    rb = np.log(pb / pb.shift(FENETRE_PERF))
    ecart = ra - rb
    sigma = ecart.rolling(FENETRE_SIGMA, min_periods=60).std()
    return ecart / sigma


def statistique_fermeture(pa, pb) -> dict | None:
    """Sur l'historique de LA paire : chaque fois que |z| a depasse le
    seuil, l'ecart s'est-il referme (|z| < 0,5) sous HORIZON_J jours ?

    Occurrences non chevauchantes : une divergence en cours n'est comptee
    qu'une fois. Retourne None si moins de OCCURRENCES_MIN occurrences —
    une statistique sur 3 cas est du bruit.
    """
    z = _ecarts_normalises(pa, pb).dropna()
    if len(z) < FENETRE_SIGMA:
        return None
    valeurs = list(z)
    n = len(valeurs)
    occurrences = fermees = 0
    delais = []
    i = 0
    while i < n - 1:
        if abs(valeurs[i]) < SEUIL_Z:
            i += 1
            continue
        # on ne compte pas la toute derniere divergence encore ouverte
        if i >= n - 1:
            break
        occurrences += 1
        ferme_a = None
        for j in range(i + 1, min(i + 1 + HORIZON_J, n)):
            if abs(valeurs[j]) < Z_FERME:
                ferme_a = j - i
                break
        if ferme_a is not None:
            fermees += 1
            delais.append(ferme_a)
            i += ferme_a
        else:
            i += HORIZON_J
        # sauter la fin de l'episode : occurrences non chevauchantes
        while i < n and abs(valeurs[i]) >= Z_FERME:
            i += 1
    if occurrences < OCCURRENCES_MIN:
        return None
    delais.sort()
    return {"occurrences": occurrences,
            "taux_fermeture_pct": round(100 * fermees / occurrences),
            "delai_median_j": delais[len(delais) // 2] if delais else None,
            "horizon_j": HORIZON_J}


def detecter(px, pivot: str, membres: list[dict],
             vigie_calme: bool = True) -> list[dict]:
    """Les opportunites de rattrapage du moment.

    px      : DataFrame de clotures quotidiennes (colonnes = tickers)
    membres : la constellation serialisee ({ticker, corr, stabilite, ...})
    vigie_calme : etat de l'agent Vigie — False marque tout « a valider »
    """
    out: list[dict] = []
    if px is None or pivot not in getattr(px, "columns", []):
        return out
    pa = px[pivot].dropna()

    for m in membres:
        tk = m.get("ticker")
        # GARDE-FOU 1 : correlation forte ET stable, sinon rien.
        if (m.get("corr", 0) < CORR_MIN
                or (m.get("stabilite") or 0) < STABILITE_MIN):
            continue
        if tk not in px.columns:
            continue
        pb = px[tk].reindex(pa.index).ffill().dropna()
        aligne_a = pa.reindex(pb.index)
        z_serie = _ecarts_normalises(aligne_a, pb).dropna()
        if not len(z_serie):
            continue
        z = float(z_serie.iloc[-1])
        if abs(z) < SEUIL_Z:
            continue
        stats = statistique_fermeture(aligne_a, pb)
        if stats is None:
            continue        # pas d'historique d'occurrences = pas d'avis
        # z > 0 : le pivot a couru, le satellite est en RETARD a la hausse.
        sens = "achat" if z > 0 else "vente"
        out.append({
            "ticker": tk, "pivot": pivot, "z": round(z, 2),
            "sens": sens,
            "corr": m.get("corr"), "stabilite": m.get("stabilite"),
            "perf5j_pivot": round(float(
                (aligne_a.iloc[-1] / aligne_a.iloc[-1 - FENETRE_PERF] - 1) * 100), 2)
            if len(aligne_a) > FENETRE_PERF else None,
            "perf5j_membre": round(float(
                (pb.iloc[-1] / pb.iloc[-1 - FENETRE_PERF] - 1) * 100), 2)
            if len(pb) > FENETRE_PERF else None,
            "historique": stats,
            "a_valider": not vigie_calme,
            "note": ("l'écart s'est refermé sous "
                     f"{stats['horizon_j']} j dans {stats['taux_fermeture_pct']} % "
                     f"des cas ({stats['occurrences']} occurrences mesurées)"),
        })
    out.sort(key=lambda x: -abs(x["z"]))
    return out
