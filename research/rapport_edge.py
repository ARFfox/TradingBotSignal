"""Lance le walk-forward sur TOUS les instruments du registre et ecrit :
- research/rapport_edge.md   — le rapport lisible
- research/verdicts.json     — {instrument: {tf: verdict}}, lu par le site

    python3 -m research.rapport_edge

Sources par instrument (via le registre, regle 13) :
- XAU/USD : Twelve Data (le cache du tableau, comme le live)
- BTC/USD, ETH/USD : Binance (sans cle, pagine)
- EUR/USD, SPY : Yahoo (1 h sur ~730 j ; 30/15/5 min sur 60 j)

Le cout de chaque instrument vient de Instrument.cout_pct (converti en
points fenetre par fenetre) — sauf l'or qui garde son 0,3 pt historique
pour rester comparable aux backtests precedents du projet.
"""
from __future__ import annotations

import datetime
import json
import warnings
from dataclasses import asdict
from pathlib import Path

warnings.filterwarnings("ignore")

DOSSIER = Path(__file__).resolve().parent

# La profondeur CALENDAIRE couverte varie enormement d'un timeframe a
# l'autre (5000 bougies M5 = ~17 jours). Le protocole peut y cocher ses
# cases sans que la preuve couvre assez de conditions de marche : on
# l'affiche, on ne le cache pas.
PROFONDEUR_MIN_JOURS = 60

def _plan() -> list[tuple]:
    """(instrument, source, timeframes) DEDUITS du registre — aucun symbole
    cite ici (regle 13) : l'instrument par defaut passe par Twelve Data
    (le cache du tableau, comme le live), les autres par leur premiere
    source declaree. Yahoo n'a pas de 4 h natif -> pas de H4."""
    from gold_agent import instruments
    defaut = instruments.par_defaut().symbole
    plan = []
    for cle, inst in instruments.REGISTRE.items():
        if cle == defaut:
            plan.append((cle, "twelvedata", ["H4", "H1", "M30", "M15", "M5"]))
            continue
        source = inst.codes[0][0] if inst.codes else "yahoo"
        tfs = (["H4", "H1", "M30", "M15", "M5"] if source in ("binance", "bybit")
               else ["H1", "M30", "M15", "M5"])
        plan.append((cle, source, tfs))
    return plan


def _bars_pour(inst, source: str, tf_code: str) -> list[dict]:
    if source == "twelvedata":
        from gold_agent import tableau
        bars, _, _ = tableau._bars_caches(inst.symbole, tf_code, 5000)
        return bars
    if source == "binance":
        from feeds.binance import Binance
        return Binance().bars(inst.code_pour("binance"), tf_code, 5000)
    if source == "yahoo":
        from feeds.yahoo import Yahoo
        return Yahoo().bars(inst.code_pour("yahoo"), tf_code, 12000)
    raise ValueError(source)


def principal() -> None:
    from gold_agent import instruments, strategy as sg, tableau
    from research import walkforward as wf

    cfg_par_nom = {c["nom"]: c for c in tableau.TIMEFRAMES}
    resultats, verdicts = [], {}

    for symbole, source, tfs in _plan():
        inst = instruments.REGISTRE[symbole]
        verdicts.setdefault(symbole, {})
        for nom_tf in tfs:
            cfg = cfg_par_nom[nom_tf]
            try:
                bars = _bars_pour(inst, source, cfg["tf"])
            except Exception as e:
                print(f"{symbole:>8} {nom_tf:>4} : donnees indisponibles ({str(e)[:60]})")
                continue
            if len(bars) < 500:
                print(f"{symbole:>8} {nom_tf:>4} : {len(bars)} bougies — trop court, ignoré")
                continue

            if symbole == instruments.par_defaut().symbole:
                p = sg.Params(**cfg["params"], cout_pts=0.3,
                              k_stop=cfg.get("k_stop", 1.0))
                r = wf.executer(bars, p, symbole, nom_tf)
            else:
                p = sg.Params(**cfg["params"], k_stop=cfg.get("k_stop", 1.0))
                r = wf.executer(bars, p, symbole, nom_tf,
                                cout_pct=inst.cout_pct)

            jours = (bars[-1]["time"] - bars[0]["time"]) / 86400 if len(bars) > 1 else 0
            note = ""
            if r.autorise and jours < PROFONDEUR_MIN_JOURS:
                note = (f"⚠️ preuve courte : {jours:.0f} j de calendrier — critères "
                        f"passés mais conditions de marché peu variées")
            resultats.append((r, note))
            verdicts[symbole][nom_tf] = {**asdict(r),
                                         "jours_calendrier": round(jours),
                                         "source": source, "note": note,
                                         "genere_le": datetime.date.today().isoformat()}
            etat = "✅ AUTORISÉ" if r.autorise else "❌ REFUSÉ"
            print(f"{symbole:>8} {nom_tf:>4} : {r.trades:>3} trades · R moyen "
                  f"{r.r_moyen:+.3f} · PF {r.profit_factor} · {etat}"
                  + (f" · {note}" if note else ""))

    lignes = [
        "# Rapport d'edge — walk-forward multi-marchés",
        f"\n*Généré le {datetime.date.today()} par `python3 -m research.rapport_edge` —"
        " fenêtres glissantes, purge 5 bougies, coûts par instrument (registre),"
        " paramètres mesurés du projet, aucune optimisation dans la boucle."
        " Une fenêtre ne vote qu'à partir de 3 trades résolus.*\n",
        "| Instrument | TF | Trades | R moyen | R total | PF | Réussite | Pire creux "
        "| Fen.+ | Régimes | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    lignes += [__import__("research.walkforward", fromlist=["ligne"]).ligne(r)
               for r, _ in resultats]
    notes = [f"- **{r.instrument} {r.tf}** : {n}" for r, n in resultats if n]
    if notes:
        lignes += ["", "## Réserves"] + notes
    lignes += [
        "", "## Lecture",
        "- Verdict CUMULATIF : ≥ 30 trades ET ≥ 2 régimes ET PF > 1,3 ET R moyen > 0 ET",
        "  ≥ 50 % des fenêtres évaluables positives. Un critère manquant → REFUSÉ.",
        "- Les coûts viennent du registre (`Instrument.cout_pct`) — estimations",
        "  prudentes à affiner par mesure sur le compte réel.",
        "- Un REFUSÉ « échantillon court / fenêtres » n'est pas un échec de la règle :",
        "  c'est une preuve qui manque encore. Le couple reste observé et testé.", "",
    ]
    (DOSSIER / "rapport_edge.md").write_text("\n".join(lignes))
    (DOSSIER / "verdicts.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=1))
    print("-> rapport_edge.md + verdicts.json écrits")


if __name__ == "__main__":
    principal()
