"""Le rapport quotidien du Chef d'orchestre (SPEC_V2 §4, recalibration 24 h).

Chaque jour, une fois : l'etat du systeme en francais lisible — signaux
emis et resolus, couleurs de la grille, verdict du Miroir, calibration
Brier, sante des agents, evenements marquants. Archive dans
~/.gold_agent_rapports/AAAA-MM-JJ.md, affiche dans l'onglet Cerveau, et
resume en UNE notification telephone (pas une par section : un rapport
qui spamme finit ignore).

Module presque pur : generer() ne lit que le paquet et le journal ;
quotidien() ajoute l'ecriture disque et le garde-fou une-fois-par-jour.
"""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

DOSSIER = Path.home() / ".gold_agent_rapports"
_MEMO = {"jour": None}

COULEUR_TXT = {"vert": "🟩", "bleu": "🟦", "gris": "⬜", "rouge": "🟥"}


def generer(paquet: dict, signaux: list | None = None) -> str:
    """Le rapport du jour, en Markdown lisible. Pur : rien n'est ecrit."""
    if signaux is None:
        try:
            from . import journal
            signaux = journal._charger()
        except Exception:
            signaux = []

    aujourdhui = dt.datetime.now(dt.timezone.utc).date()
    depuis_minuit = time.mktime(aujourdhui.timetuple())
    du_jour = [s for s in signaux if (s.get("cree_ts") or 0) >= depuis_minuit]
    resolus_jour = [s for s in signaux
                    if s.get("statut") in ("gagnant", "perdant")
                    and (s.get("cree_ts") or 0) >= depuis_minuit - 7 * 86400]

    L = [f"# Rapport du Chef — {aujourdhui:%d/%m/%Y}", ""]

    # --- etat -----------------------------------------------------------
    cons = paquet.get("consensus") or {}
    susp = paquet.get("suspension")
    L += ["## État",
          f"- Prix : **{paquet.get('prix', '—')}** · consensus "
          f"{cons.get('pct_haussier', '?')} % haussier",
          f"- Émission : {'⛔ SUSPENDUE — ' + str(susp)[:100] if susp else '✅ active'}",
          ""]

    # --- signaux --------------------------------------------------------
    L += ["## Signaux",
          f"- Émis aujourd'hui : **{len(du_jour)}**"
          + ("" if not du_jour else " — "
             + ", ".join(f"{s['tf']} {s['sens']} @ {s['entree']}" for s in du_jour[:4]))]
    if resolus_jour:
        r7 = sum(s.get("r_obtenu") or 0 for s in resolus_jour)
        g7 = sum(1 for s in resolus_jour if s["statut"] == "gagnant")
        L.append(f"- Résolus sur 7 jours : {len(resolus_jour)} "
                 f"({g7} gagnants) · {r7:+.2f}R")
    L.append("")

    # --- grille de conviction -------------------------------------------
    g = paquet.get("grille") or []
    if g:
        L.append("## Grille de conviction (90 j live · walk-forward)")
        for x in g:
            wf = x.get("walkforward") or {}
            v = ("wf ✅" if wf.get("autorise") else "wf ❌" if wf else "wf —")
            L.append(f"- {COULEUR_TXT.get(x['couleur'], '·')} **{x['tf']}** : "
                     f"{x['trades']} résolus, {x['r_cumule']:+.2f}R · {v}")
        L.append("")

    # --- miroir / constellation -----------------------------------------
    c = paquet.get("constellation") or {}
    sc = c.get("score") or {}
    if sc:
        etat = "BLOQUÉ" if sc.get("bloque") else (
            "fiable" if sc.get("fiable") else "base mince")
        L += ["## Miroir (intermarché)",
              f"- Sens testé **{c.get('sens_teste')}** : score "
              f"{sc.get('score', 0):+.2f} sur base {sc.get('base', 0):.2f} "
              f"({etat}) · {len(sc.get('confirment', []))} confirment / "
              f"{len(sc.get('contredisent', []))} contredisent",
              f"- Biais : {c.get('source_biais', '?')}", ""]

    # --- rattrapage -------------------------------------------------------
    ops = paquet.get("rattrapage") or []
    if ops:
        L += ["## Rattrapage (AG-17)"]
        L += [f"- 🎯 {o['ticker']} : écart {o['z']:+.1f} σ → piste {o['sens']} "
              f"· {o['note']}" + (" · **à valider (Vigie)**" if o.get("a_valider") else "")
              for o in ops[:3]]
        L.append("")

    # --- flux crypto -------------------------------------------------------
    fx = (paquet.get("news") or {}).get("flux_crypto") or {}
    if fx.get("disponible") and fx.get("lecture"):
        L += ["## Positionnement crypto (contexte — recouplage mesuré)"]
        L += [f"- ₿ {x}" for x in fx["lecture"]]
        L.append("")

    # --- calibration Brier ----------------------------------------------
    try:
        from . import avis
        lignes_cal = avis.resume(paquet.get("calibration") or {})
    except Exception:
        lignes_cal = []
    if lignes_cal:
        L += ["## Calibration des agents (Brier)"]
        L += [f"- {x}" for x in lignes_cal[:6]]
        L.append("")

    # --- sante ----------------------------------------------------------
    sa = paquet.get("sante") or {}
    probs = sa.get("problemes") or []
    L += ["## Santé",
          ("- Tous les agents répondent, aucun problème détecté."
           if not probs else
           "\n".join(f"- ⚠ {p[:110]}" for p in probs[:4])), ""]

    # --- evenements marquants -------------------------------------------
    evts = [e for e in (paquet.get("evenements") or [])
            if e.get("niveau") in ("veto", "alerte")]
    if evts:
        L += ["## Événements marquants"]
        L += [f"- {e['t']} · {e['agent']} : {e['texte']}" for e in evts[-6:]]
        L.append("")

    L += ["---",
          "*Rapport automatique — le système analyse et notifie, il ne "
          "passe aucun ordre. Les poids calculés ne gouvernent pas encore "
          "le consensus (validation en attente).*", ""]
    return "\n".join(L)


def quotidien(paquet: dict) -> str | None:
    """Ecrit le rapport UNE fois par jour (UTC) ; retourne le chemin si un
    nouveau rapport vient d'etre ecrit, None sinon. Une seule notification
    telephone, courte."""
    jour = dt.datetime.now(dt.timezone.utc).date().isoformat()
    if _MEMO["jour"] == jour:
        return None
    chemin = DOSSIER / f"{jour}.md"
    if chemin.exists():
        _MEMO["jour"] = jour
        return None
    texte = generer(paquet)
    try:
        DOSSIER.mkdir(exist_ok=True)
        chemin.write_text(texte)
    except Exception:
        return None
    _MEMO["jour"] = jour
    try:
        from . import notify
        cons = paquet.get("consensus") or {}
        susp = "⛔ suspendue" if paquet.get("suspension") else "✅ active"
        notify.pousser_telephone(
            "Rapport quotidien du Chef",
            f"{paquet.get('prix', '—')} · consensus "
            f"{cons.get('pct_haussier', '?')}% haussier · émission {susp} · "
            f"détail sur le site (Cerveau)")
    except Exception:
        pass
    return str(chemin)


def dernier() -> str | None:
    """Le contenu du rapport le plus recent, pour l'affichage du site."""
    try:
        fichiers = sorted(DOSSIER.glob("*.md"))
        return fichiers[-1].read_text() if fichiers else None
    except Exception:
        return None
