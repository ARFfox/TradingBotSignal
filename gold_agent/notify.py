"""Notifications : système (macOS) et push vers le téléphone (ntfy.sh).

Aucun ordre n'est passé. Le message contient les paramètres calculés par la
règle, mis en forme pour être saisis en quelques secondes dans MetaTrader 5
mobile. La décision et la saisie restent celles de l'opérateur.
"""
from __future__ import annotations

import json
import shutil
import subprocess

from . import datasource as ds

from . import instruments as _instr


def _conf(nom: str, defaut: str = "") -> str:
    import os
    return os.environ.get(nom) or ds._charger_env().get(nom, defaut)


def taille_position(entree: float, stop: float,
                    instrument: "_instr.Instrument | None" = None) -> dict | None:
    """Lots correspondant au risque configuré. Sans capital renseigné, rien."""
    try:
        capital = float(_conf("CAPITAL", "") or 0)
        risque_pct = float(_conf("RISQUE_PCT", "1") or 1)
    except ValueError:
        return None
    if capital <= 0:
        return None
    distance = abs(entree - stop)
    if distance <= 0:
        return None
    montant = capital * risque_pct / 100.0
    instrument = instrument or _instr.par_defaut()
    lots = montant / (distance * instrument.point_par_lot)
    return {"lots": round(lots, 2), "lots_precis": round(lots, 4),
            "risque_montant": round(montant, 2), "capital": capital,
            "risque_pct": risque_pct, "distance_pts": round(distance, 2)}


def ticket(tf: str, s: dict, prix: float, fiabilite: str) -> str:
    """Ordre mis en forme pour saisie manuelle dans MT5."""
    sens = s["setup"]
    type_ordre = ("Buy Limit" if sens == "achat" else "Sell Limit") \
        if not s.get("declenche") else ("Buy" if sens == "achat" else "Sell")

    l = [f"Symbole   XAUUSD",
         f"Type      {type_ordre}",
         f"Prix      {s['entree']}",
         f"SL        {s['stop']}",
         f"TP        {s['objectif']}",
         f"R:R       {s['rr']}"]

    t = taille_position(s["entree"], s["stop"])
    if t:
        l.append(f"Volume    {t['lots']} lot  (risque {t['risque_montant']} "
                 f"= {t['risque_pct']}% de {t['capital']})")
    else:
        l.append("Volume    — renseigne CAPITAL dans .env pour le calcul")

    l.append("")
    l.append(f"Prix actuel {prix} · timeframe {tf}")
    l.append(f"Fiabilite : {fiabilite}")
    if fiabilite != "mesuré":
        l.append("/!\\ Ce timeframe n'a pas de backtest solide derriere lui.")
    if sens == "vente":
        l.append("/!\\ Cote vendeur non valide : 5 trades, esperance negative.")
    l.append("")
    l.append("Aucun ordre n'a ete passe. Saisie manuelle requise.")
    return "\n".join(l)


def svg_vers_png(svg: str) -> str | None:
    """Convertit un SVG en PNG via qlmanage (outil systeme macOS).

    Idee retenue d'un reel du 07/09 : un signal accompagne de son graphique
    se juge d'un coup d'oeil sur le telephone, sans ouvrir le site.
    """
    import tempfile, os
    try:
        d = tempfile.mkdtemp(prefix="gold_notif_")
        chemin_svg = os.path.join(d, "signal.svg")
        with open(chemin_svg, "w") as f:
            f.write(svg)
        subprocess.run(["qlmanage", "-t", "-s", "900", "-o", d, chemin_svg],
                       capture_output=True, timeout=30)
        png = chemin_svg + ".png"
        return png if os.path.exists(png) else None
    except Exception:
        return None


def pousser_telephone(titre: str, corps: str, urgent: bool = False,
                      image: str | None = None) -> bool:
    """Push via ntfy.sh vers le sujet configure."""
    sujet = _conf("NTFY_TOPIC")
    if not sujet:
        return False
    serveur = _conf("NTFY_SERVEUR", "https://ntfy.sh").rstrip("/")
    entetes = [
        "-H", f"Title: {titre}",
        "-H", f"Priority: {'urgent' if urgent else 'high'}",
        "-H", "Tags: chart_with_upwards_trend,coin",
    ]
    try:
        if image:
            # Piece jointe : le fichier part en PUT, le texte passe en en-tetes.
            # Les en-tetes HTTP refusent les retours a la ligne : legende
            # compactee sur une ligne (le ticket complet part par la
            # notification systeme).
            legende = " · ".join(l.strip() for l in corps.splitlines() if l.strip())[:500]
            p = subprocess.run(["curl", "-s", "-m", "30", "-T", image,
                                f"{serveur}/{sujet}",
                                "-H", f"X-Title: {titre}",
                                "-H", f"X-Message: {legende}",
                                "-H", f"X-Priority: {'urgent' if urgent else 'high'}",
                                "-H", "X-Filename: signal.png"],
                               capture_output=True, text=True, timeout=40)
        else:
            p = subprocess.run(["curl", "-s", "-m", "15", "-X", "POST",
                                f"{serveur}/{sujet}", *entetes, "-d", corps],
                               capture_output=True, text=True, timeout=25)
        return p.returncode == 0 and '"id"' in p.stdout
    except Exception:
        return False


def notifier_systeme(titre: str, sous_titre: str, corps: str) -> bool:
    """Notification macOS. Fonctionne meme navigateur ferme."""
    if not shutil.which("osascript"):
        return False
    def echapper(t: str) -> str:
        return t.replace("\\", "\\\\").replace('"', '\\"')
    # osascript n'accepte pas les retours a la ligne dans une notification
    corps = " · ".join(x for x in corps.splitlines() if x.strip())[:240]
    script = (f'display notification "{echapper(corps)}" '
              f'with title "{echapper(titre)}" '
              f'subtitle "{echapper(sous_titre)}" sound name "Glass"')
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def diffuser(tf: str, s: dict, prix: float, fiabilite: str,
             svg: str | None = None) -> dict:
    """Envoie sur tous les canaux configures. Renvoie ce qui a abouti."""
    sens = s["setup"].upper()
    etat = "DECLENCHE" if s.get("declenche") else "en attente"
    titre = f"{sens} {tf} — {etat}"
    corps = ticket(tf, s, prix, fiabilite)
    image = svg_vers_png(svg) if svg else None
    return {
        "systeme": notifier_systeme(titre, f"XAU/USD {prix} · {fiabilite}", corps),
        "telephone": pousser_telephone(titre, corps,
                                       urgent=bool(s.get("declenche")), image=image),
        "image_jointe": bool(image),
    }


def etat_canaux() -> dict:
    return {
        "systeme": bool(shutil.which("osascript")),
        "telephone": bool(_conf("NTFY_TOPIC")),
        "sujet": _conf("NTFY_TOPIC") or None,
        "capital_configure": bool(_conf("CAPITAL")),
    }
