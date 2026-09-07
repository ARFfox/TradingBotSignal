"""AG-16 — L'Avocat du diable.

Il cherche ACTIVEMENT les raisons pour lesquelles un setup va echouer,
et vote toujours contre. Sa valeur : forcer le reste du systeme a etre
meilleur. Un signal ne sort que si ses objections MAJEURES sont refutees.

Module volontairement pur : aucune lecture reseau, aucune lecture disque.
On lui passe les donnees (setup, journal, agenda) et il rend un verdict —
c'est ce qui permet de le tester sans internet, comme constellation_agent.

Objections cherchees (spec v2, §6 devils-advocate) :
- niveau majeur contraire a moins de 1 ATR de l'entree
- news USD a fort impact dans la fenetre de vie estimee du trade
- ce meme setup (tf + sens) a deja echoue en serie ce mois-ci
- stop mecaniquement dans le bruit (< 0.8 ATR)
- entree en poursuite d'un mouvement deja etendu (surachat/survente)

Chaque objection porte un critere de refutation explicite. Une objection
majeure NON refutee bloque le signal ; les mineures sont affichees.
"""
from __future__ import annotations

import time

# Duree de vie typique d'un trade par timeframe : fenetre pendant laquelle
# une publication a fort impact peut invalider les stops calcules.
FENETRE_NEWS_H = {"H4": 8.0, "H1": 4.0, "M30": 2.0, "M15": 1.0, "M5": 1.0}
SEUIL_SERIE_ECHECS = 3          # perdants sur 30 j, meme tf + meme sens
SEUIL_STOP_ATR = 0.8            # stop plus proche que ca = dans le bruit
SEUIL_NIVEAU_ATR = 1.0          # niveau contraire plus proche que 1 ATR


def _obj(gravite: str, quoi: str, refutation: str, refutee: bool) -> dict:
    return {"gravite": gravite, "quoi": quoi,
            "refutation": refutation, "refutee": refutee}


def examiner(r: dict, signaux: list | None = None,
             evenements: list | None = None,
             maintenant: float | None = None) -> dict | None:
    """Examine le setup d'un timeframe. None si pas de setup actif.

    r          : dict du timeframe (setup, atr, ict, extension, nom)
    signaux    : entrees brutes du journal (tf, sens, statut, cree_ts)
    evenements : sortie de news.prochains() (titre, dans_minutes)
    """
    st = r.get("setup") or {}
    if not st.get("setup"):
        return None
    sens = st["setup"]
    entree = st.get("entree") or 0.0
    objectif = st.get("objectif") or 0.0
    stop = st.get("stop") or 0.0
    atr = r.get("atr") or 0.0
    objections: list[dict] = []

    # 1. Niveau majeur contraire a moins de 1 ATR de l'entree ----------------
    pd_ = (r.get("ict") or {}).get("premium_discount") or {}
    if atr > 0 and entree:
        if sens == "achat" and pd_.get("haut_range"):
            niveau, dist = pd_["haut_range"], pd_["haut_range"] - entree
            if 0 < dist < SEUIL_NIVEAU_ATR * atr:
                refutee = bool(objectif) and objectif <= niveau
                objections.append(_obj(
                    "majeure",
                    f"résistance majeure à {niveau:.2f}, à {dist:.1f} pt "
                    f"({dist / atr:.1f} ATR) au-dessus de l'entrée",
                    "le TP est atteint avant ce niveau",
                    refutee))
        elif sens == "vente" and pd_.get("bas_range"):
            niveau, dist = pd_["bas_range"], entree - pd_["bas_range"]
            if 0 < dist < SEUIL_NIVEAU_ATR * atr:
                refutee = bool(objectif) and objectif >= niveau
                objections.append(_obj(
                    "majeure",
                    f"support majeur à {niveau:.2f}, à {dist:.1f} pt "
                    f"({dist / atr:.1f} ATR) sous l'entrée",
                    "le TP est atteint avant ce niveau",
                    refutee))

    # 2. News a fort impact dans la fenetre de vie du trade ------------------
    fenetre_h = FENETRE_NEWS_H.get(r.get("nom", ""), 2.0)
    for e in (evenements or []):
        mn = e.get("dans_minutes")
        if mn is not None and -30 <= mn <= fenetre_h * 60:
            objections.append(_obj(
                "majeure",
                f"{e.get('titre', 'événement USD')} dans "
                f"{max(0, round(mn))} min — dans la fenêtre de vie du trade "
                f"({r.get('nom')} ≈ {fenetre_h:g} h)",
                "attendre la publication : irréfutable avant le chiffre",
                False))
            break                                  # une suffit pour bloquer

    # 3. Serie d'echecs recente sur ce meme setup ----------------------------
    if signaux:
        depuis = (maintenant or time.time()) - 30 * 86400
        recents = [x for x in signaux
                   if x.get("tf") == r.get("nom") and x.get("sens") == sens
                   and (x.get("cree_ts") or 0) >= depuis
                   and x.get("statut") in ("gagnant", "perdant")]
        perdus = sum(1 for x in recents if x["statut"] == "perdant")
        gagnes = len(recents) - perdus
        if perdus >= SEUIL_SERIE_ECHECS:
            refutee = gagnes > 0
            objections.append(_obj(
                "majeure" if not refutee else "mineure",
                f"ce setup ({r.get('nom')} {sens}) a échoué {perdus} fois "
                f"sur 30 jours ({gagnes} réussite{'s' if gagnes > 1 else ''})",
                "au moins une réussite récente sur le même setup",
                refutee))

    # 4. Stop dans le bruit --------------------------------------------------
    if atr > 0 and entree and stop:
        d_stop = abs(entree - stop)
        if d_stop < SEUIL_STOP_ATR * atr:
            objections.append(_obj(
                "mineure",
                f"stop à {d_stop:.1f} pt ({d_stop / atr:.1f} ATR) : "
                f"dans le bruit normal de la bougie",
                "élargir le stop ou passer ce signal",
                False))

    # 5. Entree en poursuite d'un mouvement deja etendu ----------------------
    ext = r.get("extension") or {}
    meme_sens = {"achat": "haussiere", "vente": "baissiere"}.get(sens)
    if ext.get("niveau") in ("forte", "extreme") and \
            str(ext.get("sens", "")).replace("è", "e") == meme_sens:
        objections.append(_obj(
            "mineure",
            f"entrée en poursuite : extension {ext['sens']} déjà "
            f"{ext['niveau']} (score {ext.get('score')})",
            "attendre un repli vers la zone d'entrée",
            False))

    majeures = [o for o in objections if o["gravite"] == "majeure"
                and not o["refutee"]]
    return {
        "objections": objections,
        "verdict": "non_refute" if majeures else "refute",
        "motif_blocage": majeures[0]["quoi"] if majeures else None,
    }
