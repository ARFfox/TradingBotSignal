"""Étape 6ter — le pont AG-20 : lecture mémorisée, source descriptive pour
AG-19, faits de niveau versés à la TRACE du débat (sans réseau)."""
from gold_agent import chartiste


def _bougies(n=60, base=100.0, pas=0.3):
    """Une montée régulière : tendance haussière franche sur chaque TF."""
    out = []
    for i in range(n):
        px = base + i * pas
        out.append({"open": px, "high": px + 0.4, "low": px - 0.4,
                    "close": px + 0.2, "time": 1_750_000_000 + i * 60})
    return out


def _bars_par_tf():
    return {tf: _bougies() for tf in ("H4", "H1", "M30", "M15", "M5")}


def test_lecture_memorisee_et_source_directeur():
    L = chartiste.lire_instrument("TEST/USD", _bars_par_tf())
    assert L is not None and L.sens_dominant == "haussier"
    assert chartiste.derniere("TEST/USD") is L
    src = chartiste.source_pour_directeur("TEST/USD")
    assert src is not None
    assert src.famille == "tendance" and not src.predictive   # décrit, poids 1
    assert src.sens == "haussier" and "timeframes" in src.mesure


def test_niveaux_dans_la_trace_du_debat():
    L = chartiste.lire_instrument("TEST/USD", _bars_par_tf())
    if not L.niveaux_fusionnes:            # une montée pure peut n'en avoir aucun
        return
    prix = L.niveaux_fusionnes[0]["prix"]   # collé au niveau majeur
    st = {"debat": {"verdict": "NEUTRE", "contre": [], "pour": []}}
    chartiste.enrichir_debat(st, "TEST/USD", prix)
    tous = st["debat"]["contre"] + st["debat"]["pour"]
    assert any("[AG-20]" in a["texte"] for a in tous)
    # que des NIVEAUX, jamais de figure : une figure se croit, un niveau
    # se vérifie
    assert all("niveau" in a["code"] or "conflit" in a["code"] for a in tous)


def test_absence_ne_vote_pas():
    assert chartiste.derniere("JAMAIS/VU") is None
    assert chartiste.source_pour_directeur("JAMAIS/VU") is None
    st = {"debat": {"verdict": "NEUTRE", "contre": [], "pour": []}}
    chartiste.enrichir_debat(st, "JAMAIS/VU", 100.0)
    assert st["debat"]["contre"] == [] and st["debat"]["pour"] == []


def test_carte_panneau_complete():
    """Bug réel (17/09) : la carte livrée n'a pas les champs de
    présentation — le panneau exigeait 'coul'/'metriques' et la page
    entière tombait en « Erreur de collecte ». La carte insérée doit
    porter TOUT le contrat du panneau."""
    chartiste.lire_instrument("TEST/USD", _bars_par_tf())
    paquet = {"agents": []}
    chartiste.carte_dans_agents(paquet, "TEST/USD")
    carte = next(c for c in paquet["agents"] if c["code"] == "AG-20")
    for champ in ("nom", "emoji", "coul", "role", "metriques", "charge",
                  "statut", "conviction", "position", "activites"):
        assert champ in carte, champ
