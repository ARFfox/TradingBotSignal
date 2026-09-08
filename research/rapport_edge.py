"""Lance le walk-forward sur XAU/USD (5 timeframes) et ecrit :
- research/rapport_edge.md   — le rapport lisible
- research/verdicts.json     — les verdicts, lus par le site (grille)

    python3 -m research.rapport_edge

Utilise le cache de bougies du tableau : relance-le apres une periode de
surveillance pour des fenetres plus fraiches. Duree : ~1 minute.
"""
from __future__ import annotations

import datetime
import json
import warnings
from dataclasses import asdict
from pathlib import Path

warnings.filterwarnings("ignore")

DOSSIER = Path(__file__).resolve().parent

# La profondeur CALENDAIRE couverte par 5000 bougies varie enormement d'un
# timeframe a l'autre : en M5 c'est ~3 semaines. Le protocole peut y cocher
# ses cases (trades, regimes intra-jour) sans que la preuve couvre assez de
# conditions de marche. On l'affiche, on ne le cache pas.
PROFONDEUR_MIN_JOURS = 60


def principal() -> None:
    from gold_agent import instruments, strategy as sg, tableau
    from research import walkforward as wf

    inst = instruments.par_defaut()
    resultats, verdicts = [], {}
    for cfg in tableau.TIMEFRAMES:
        bars, _, _ = tableau._bars_caches(inst.symbole, cfg["tf"], 5000)
        p = sg.Params(**cfg["params"], cout_pts=0.3, k_stop=cfg.get("k_stop", 1.0))
        r = wf.executer(bars, p, inst.symbole, cfg["nom"])
        jours = (bars[-1]["time"] - bars[0]["time"]) / 86400 if len(bars) > 1 else 0
        note = ""
        if r.autorise and jours < PROFONDEUR_MIN_JOURS:
            note = (f"⚠️ preuve courte : {jours:.0f} j de calendrier seulement — "
                    f"critères passés mais conditions de marché peu variées")
        resultats.append((r, note))
        verdicts[r.tf] = {**asdict(r), "jours_calendrier": round(jours),
                          "note": note,
                          "genere_le": datetime.date.today().isoformat()}
        etat = "✅ AUTORISÉ" if r.autorise else "❌ REFUSÉ"
        print(f"{r.tf:>4} : {r.trades:>3} trades · R moyen {r.r_moyen:+.3f} · "
              f"PF {r.profit_factor} · {etat}" + (f" · {note}" if note else ""))

    lignes = [
        "# Rapport d'edge — walk-forward XAU/USD",
        f"\n*Généré le {datetime.date.today()} par `python3 -m research.rapport_edge` —"
        " fenêtres glissantes, purge 5 bougies, coût 0,3 pt/trade, paramètres mesurés"
        " du projet (aucune optimisation dans la boucle). Une fenêtre ne vote qu'à"
        " partir de 3 trades résolus.*\n",
        "| Instrument | TF | Trades | R moyen | R total | PF | Réussite | Pire creux "
        "| Fen.+ | Régimes | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    lignes += [wf.ligne(r) for r, _ in resultats]
    notes = [f"- **{r.tf}** : {n}" for r, n in resultats if n]
    if notes:
        lignes += ["", "## Réserves"] + notes
    lignes += [
        "", "## Lecture",
        "- Verdict CUMULATIF : ≥ 30 trades ET ≥ 2 régimes ET PF > 1,3 ET R moyen > 0 ET",
        "  ≥ 50 % des fenêtres évaluables positives. Un critère manquant → REFUSÉ.",
        "- Un REFUSÉ « échantillon court / fenêtres » n'est pas un échec de la règle :",
        "  c'est une preuve qui manque encore. Le couple reste observé et testé.",
        "- Les autres instruments (BTC, EUR/USD, SPY…) attendent leurs adapters intraday",
        "  (phase 3) : le protocole les recevra tel quel.", "",
    ]
    (DOSSIER / "rapport_edge.md").write_text("\n".join(lignes))
    (DOSSIER / "verdicts.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=1))
    print("-> rapport_edge.md + verdicts.json écrits")


if __name__ == "__main__":
    principal()
