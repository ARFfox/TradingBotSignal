"""Le passage à l'émission — débat contradictoire puis anti-contradiction.

Extrait de tableau.py (règle 15 : aucun fichier > 500 lignes) : ces deux
étapes d'APPLIQUER (6 puis 3) sont le goulot par lequel TOUT signal or
passe avant d'entrer au journal. Le multi a son propre câblage dans
multi.py — même modules, mêmes règles.
"""
from __future__ import annotations

import time


def debattre(st: dict, r: dict, resultats: list, symbole: str,
             prix_actuel: float | None, evts_agenda: list,
             carreau: dict | None, evt) -> None:
    """APPLIQUER étape 6 : les avocats plaident sur des FAITS. BLOQUÉ pose
    `refus_emission` sur le setup (motif visible) ; sinon le facteur du
    débat multiplie la note. Ne lève jamais — un débat en panne s'annonce."""
    from . import debat as _debat, instruments
    try:
        confluence = sum(1 for x in resultats
                         if (x.get("setup") or {}).get("setup") == st["setup"])
        minutes = [e.get("dans_minutes") for e in evts_agenda
                   if e.get("dans_minutes") is not None]
        v = _debat.examiner_setup(
            st, instrument=symbole, tf=r["nom"], atr=r.get("atr"),
            spread=(prix_actuel or 0) * instruments.par_defaut().cout_pct / 100,
            intermarche=st.get("intermarche"), confluence=confluence,
            news_dans_h=(min(minutes) / 60.0) if minutes else None,
            carreau=carreau, poids=_debat.poids_arguments())
        if v.bloque:
            st["refus_emission"] = ("débat : "
                                    + (v.contre[0].texte if v.contre
                                       else v.explication))
            evt("Superviseur", f"{r['nom']} {st['setup']} BLOQUÉ par le "
                f"débat — {st['refus_emission'][:80]}", "veto")
    except Exception as e:
        evt("Superviseur", f"débat indisponible : {str(e)[:60]}", "warn")
    # Étape 6bis : AG-19 attache la DIRECTION (ou l'aveu qu'il n'y en a
    # pas) — sources, certitude, point de bascule. Jamais bloquant.
    from . import directeur
    directeur.analyser(st, r, instrument=symbole, tf=r["nom"],
                       marche=instruments.par_defaut().marche)


_CACHE_POIDS = {"t": 0.0, "poids": {}}


def poids_note() -> dict:
    """CHANTIER #7 : les poids mesurés (calibrage persisté) pour
    decision.noter — relus du disque au plus toutes les 60 s."""
    import time as _t
    if _t.time() - _CACHE_POIDS["t"] > 60:
        try:
            from .apprentissage import calibrage_actuel
            _CACHE_POIDS["poids"] = calibrage_actuel().get("poids_agents") or {}
        except Exception:
            pass
        _CACHE_POIDS["t"] = _t.time()
    return _CACHE_POIDS["poids"]


def emettre_lot(resultats: list, symbole: str, prix_actuel: float | None,
                evt) -> None:
    """APPLIQUER étape 3 : le LOT des timeframes passe par l'anti-
    contradiction avant d'entrer au journal. Un refus reste VISIBLE
    (motif sur la carte + console) mais n'est ni journalisé ni notifié."""
    from garde_fous import filtrer_lot
    from . import instruments, journal
    maintenant_ts = int(time.time())
    candidats = []
    from .apprentissage import refus_calibrage
    for r in resultats:
        st = r.get("setup") or {}
        if not st.get("setup") or st.get("refus_emission"):
            continue
        # CHANTIER #8-9 : couple à espérance mesurée négative, ou note sous
        # le seuil mesuré (s'il existe — « aucun seuil » ne filtre rien).
        note_pct = (st.get("decision_chef") or {}).get("pct", 0)
        motif = refus_calibrage(symbole, r["nom"], note_pct)
        if motif:
            st["refus_emission"] = motif
            evt("Superviseur", f"{r['nom']} {st['setup']} NON émis — {motif}",
                "veto")
            continue
        candidats.append({"instrument": symbole, "tf": r["nom"],
                          "sens": st["setup"], "note": note_pct,
                          "cree_ts": maintenant_ts, "_r": r})
    gardes, refuses = filtrer_lot(candidats)
    for c in refuses:
        st = c["_r"]["setup"]
        st["refus_emission"] = c["motif"]
        evt("Superviseur", f"{c['tf']} {c['sens']} NON émis — {c['motif']}",
            "veto")
    for c in gardes:
        r = c["_r"]
        journal.enregistrer(r["nom"], r["setup"], prix_actuel or 0,
                            (r.get("fiabilite") or {}).get("niveau", "?"),
                            atr=r.get("atr"),
                            spread=(prix_actuel or 0)
                            * instruments.par_defaut().cout_pct / 100)


def construire_graphe(paquet: dict, resultats: list) -> dict:
    """APPLIQUER étape 7 : le graphe montre les POSITIONS sur le signal de
    référence (le mieux noté de la passe). Défaut « neutre », jamais
    « pour » ; la position vient de l'avis directionnel, JAMAIS de la
    conviction seule."""
    from graphe_agents import construire
    reference = None
    for r in resultats:
        st = r.get("setup") or {}
        if st.get("setup") and (reference is None
                                or (st.get("decision_chef") or {}).get("pct", 0)
                                > (reference.get("decision_chef") or {}).get("pct", 0)):
            reference = st
    avocat, defense, positions = None, None, {}
    if reference:
        d = reference.get("debat") or {}
        if d.get("contre"):
            avocat = {"cible": "AG-03",
                      "objections": [a["texte"] for a in d["contre"]],
                      "bloque": d.get("verdict") == "BLOQUÉ"}
        if d.get("pour"):
            defense = {"cible": "AG-03",
                       "arguments": [a["texte"] for a in d["pour"]]}
        positions = {"AG-16": "contre" if d.get("contre") else "neutre",
                     "AG-18": "pour" if d.get("pour") else "neutre"}
        for code, sens_avis in (reference.get("avis") or {}).items():
            if sens_avis in ("achat", "vente"):
                positions[code] = ("pour" if sens_avis == reference["setup"]
                                   else "contre")
    cartes = [{**c, "position": positions[c["code"]]}
              if c.get("code") in positions else c
              for c in paquet.get("agents") or []]
    return construire(
        cartes=cartes,
        intermarches=(paquet.get("marches") or {}).get("graphe"),
        miroir=(paquet.get("constellation") or {}).get("score"),
        avocat=avocat, defense=defense,
    ).json()
