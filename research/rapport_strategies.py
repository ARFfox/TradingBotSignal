"""Walk-forward des 4 strategies du skill strategies-entree.

    python3 -m research.rapport_strategies

C'est l'etape 6 du skill — « la seule qui a de la valeur ». Les etapes
1 a 5 ont produit des candidats (CRT, IFVG, ORB, retest POC) ; celle-ci
dit lesquels servent. Sans elle : quatre nouvelles facons de perdre de
l'argent avec conviction.

Ecrit : research/rapport_strategies.md + strategies_verdicts.json.
Aucune strategie n'emet quoi que ce soit : verdict d'abord.
"""
from __future__ import annotations

import datetime
import json
import warnings
from dataclasses import asdict
from pathlib import Path

warnings.filterwarnings("ignore")

DOSSIER = Path(__file__).resolve().parent


def _plan():
    """(strategie, detecteur, [(instrument, tf), ...]) — l'ORB et le CRT ont
    besoin d'une session/heure de reference : pas de crypto pour l'ORB
    (sessions refusees), CRT teste sur H1 seulement (sa bougie de reference
    est horaire). Le POC utilise le vrai volume sur BTC et un profil de
    TEMPS sur l'or (annonce) — le verdict departage."""
    from gold_agent import instruments, strategies_entree as se, \
        strategies_volume as sv
    # Les symboles viennent du registre (regle 13) : l'or est l'instrument
    # par defaut, le crypto de reference est le premier du marche crypto.
    OR = instruments.par_defaut().symbole
    BTC = instruments.par_marche("crypto")[0].symbole
    return [
        ("CRT", se.crt, [(OR, "H1"), (BTC, "H1")]),
        ("IFVG", se.ifvg, [(OR, "H1"), (OR, "M30"), (OR, "M15"),
                           (BTC, "H1"), (BTC, "M30"), (BTC, "M15")]),
        ("ORB", sv.orb, [(OR, "M15"), (OR, "M5")]),
        ("POC_RETEST", sv.poc_retest, [(OR, "M30"), (OR, "M15"),
                                       (BTC, "M30"), (BTC, "M15")]),
    ]


def principal() -> None:
    from gold_agent import instruments, strategy as sg, tableau
    from research import walkforward as wf

    tf_codes = {c["nom"]: c["tf"] for c in tableau.TIMEFRAMES}
    p = sg.Params(ema_fast=20, ema_slow=50)      # les scanners s'auto-parametrent
    resultats, verdicts = [], {}

    for nom_strat, detecteur, couples in _plan():
        verdicts.setdefault(nom_strat, {})
        for symbole, nom_tf in couples:
            inst = instruments.REGISTRE[symbole]
            defaut = symbole == instruments.par_defaut().symbole
            try:
                if defaut:
                    bars, _, _ = tableau._bars_caches(symbole, tf_codes[nom_tf], 5000)
                else:
                    from feeds.binance import Binance
                    bars = Binance().bars(inst.code_pour("binance"),
                                          tf_codes[nom_tf], 5000)
            except Exception as e:
                print(f"{nom_strat:>10} {symbole:>8} {nom_tf:>4} : donnees KO ({str(e)[:50]})")
                continue
            if len(bars) < 800:
                print(f"{nom_strat:>10} {symbole:>8} {nom_tf:>4} : {len(bars)} bougies — ignoré")
                continue
            import dataclasses
            p_ = dataclasses.replace(p, cout_pts=0.3) if defaut else p
            r = wf.executer(bars, p_, symbole, nom_tf,
                            cout_pct=None if defaut else inst.cout_pct,
                            detecteur=detecteur)
            r.instrument = f"{nom_strat} · {symbole}"
            jours = (bars[-1]["time"] - bars[0]["time"]) / 86400 if len(bars) > 1 else 0
            if r.autorise and jours < 60:
                r.motif += (f" · ⚠️ preuve courte : {jours:.0f} j de calendrier — "
                            f"et 14 candidats testés : un faux positif est "
                            f"statistiquement attendu. À reconfirmer hors "
                            f"échantillon avant toute question d'émission.")
            resultats.append(r)
            verdicts[nom_strat][f"{symbole}|{nom_tf}"] = {
                **asdict(r), "genere_le": datetime.date.today().isoformat()}
            etat = "✅ AUTORISÉ" if r.autorise else "❌ REFUSÉ"
            print(f"{nom_strat:>10} {symbole:>8} {nom_tf:>4} : {r.trades:>3} trades · "
                  f"R moyen {r.r_moyen:+.3f} · PF {r.profit_factor} · {etat}")

    lignes = [
        "# Walk-forward des stratégies du skill (CRT · IFVG · ORB · POC)",
        f"\n*Généré le {datetime.date.today()} par `python3 -m research.rapport_strategies`."
        " Ces méthodes viennent de comptes Instagram : populaires n'est pas profitables,"
        " et le corpus ne montre jamais ce qui arrive quand le setup échoue. Ce tableau"
        " est la partie qui manquait. Aucune stratégie n'émet sans verdict AUTORISÉ.*\n",
        "| Stratégie · Instrument | TF | Trades | R moyen | R total | PF | Réussite "
        "| Pire creux | Fen.+ | Régimes | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    lignes += [wf.ligne(r) for r in resultats]
    lignes += [
        "", "## Lecture",
        "- Même protocole que la règle du projet : fenêtres glissantes, purge,",
        "  coûts réels, ≥ 30 trades, ≥ 2 régimes, PF > 1,3, fenêtres évaluables.",
        "- Un RÉFUSÉ « peu de trades » sur CRT/ORB est attendu : une occasion par",
        "  jour au mieux — l'échantillon se construit avec l'historique.",
        "- Sur l'or, le profil volume est un profil de TEMPS (volume absent chez",
        "  Twelve Data) : le verdict juge cette dégradation aussi.",
        "- ⚠️ COMPARAISONS MULTIPLES : 14 couples testés — au niveau de ces seuils,",
        "  UN survivant peut être un coup de chance. Le seul AUTORISÉ (POC · or M15)",
        "  repose sur ~52 jours de calendrier : il doit se reconfirmer sur les",
        "  semaines qui viennent (relancer ce rapport) avant d'exister ailleurs",
        "  que dans ce tableau. Un candidat n'est pas un signal.", "",
    ]
    (DOSSIER / "rapport_strategies.md").write_text("\n".join(lignes))
    (DOSSIER / "strategies_verdicts.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=1))
    print("-> rapport_strategies.md + strategies_verdicts.json écrits")


if __name__ == "__main__":
    principal()
