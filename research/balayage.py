"""Pilote du balayage VectorBT (CHANTIER #11) — `python3 -m research.balayage`.

Rôle : exporter les bougies et LES entrées de la stratégie du système
(strategy.detecter — jamais une copie qui divergerait), lancer le balayage
vectorisé dans `.venv-recherche` (VectorBT exige numba, absent de
Python 3.14), et écrire `rapport_balayage.md`.

Ce que le rapport EST : une carte des multiples d'ATR du stop, espérance en
R sur le train ET sur le test (découpe chronologique). Ce qu'il N'EST PAS :
une autorisation d'émettre — la règle 3 (walk-forward complet) reste le
seul juge avant qu'un réglage touche l'émission, et l'application d'un
réglage reste un clic de Mushine.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
RAPPORT = RACINE / "rapport_balayage.md"
VENV_PY = RACINE / ".venv-recherche" / "bin" / "python"
SCRIPT = RACINE / "research" / "balayage_vbt.py"
DOSSIER = Path.home() / ".gold_agent_balayage"

MULTIPLES = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]   # stop >= 1 ATR, règle 4
RR = 2.0
FEES, SLIPPAGE = 0.0005, 0.0002                     # paramètres, pas options
PART_TEST = 0.30
BARS = 5000     # M15 : ~52 jours ; le test (30 %) garde un effectif réel
TF_BALAYES = ("60", "30", "15")


def _colonnes(limite: int | None = None) -> list[dict]:
    """Les colonnes du balayage : crypto (historique CCXT profond) sur les
    timeframes émetteurs. L'or n'y passe pas — quota Twelve Data."""
    from gold_agent import instruments, strategy as sg
    from gold_agent.analyse import bars_instrument
    from gold_agent.indicators import atr as calc_atr
    from gold_agent.tableau import TIMEFRAMES

    specs = {s["tf"]: s for s in TIMEFRAMES}
    cryptos = [i for i in instruments.REGISTRE.values()
               if i.code_pour("binance") != i.symbole]
    if limite:
        cryptos = cryptos[:limite]
    out = []
    for inst in cryptos:
        for tf in TF_BALAYES:
            spec = specs.get(tf)
            if spec is None:
                continue
            try:
                bars = bars_instrument(inst, tf, BARS)
            except Exception:
                continue
            if len(bars) < 400:
                continue
            p = sg.Params(k_stop=spec.get("k_stop", 1.0),
                          facteur_superieur=spec["mtf"],
                          decimales=inst.decimales, **spec["params"])
            signaux = sg.detecter(bars, p)
            if len(signaux) < 8:
                continue                    # trop peu pour dire quoi que ce soit
            h = [b["high"] for b in bars]
            l = [b["low"] for b in bars]
            c = [b["close"] for b in bars]
            a = calc_atr(h, l, c, 14)
            out.append({
                "cle": f"{inst.symbole}|{spec['nom']}",
                "close": c,
                "atr_frac": [(x / y) if (x and y) else 0.0
                             for x, y in zip(a, c)],
                "achats": [s.index for s in signaux if s.sens == "achat"],
                "ventes": [s.index for s in signaux if s.sens == "vente"],
            })
    return out


def _tableau(res: dict) -> list[str]:
    o = [f"### {res['cle']}", "",
         "| stop (×ATR) | n train | E train (R) | n test | E test (R) |",
         "|---|---:|---:|---:|---:|"]
    for l in res["lignes"]:
        e_tr = f"{l['e_train']:+.2f}" if l["e_train"] is not None else "—"
        e_te = f"{l['e_test']:+.2f}" if l["e_test"] is not None else "—"
        m = res.get("meilleur_train")
        fleche = " ←" if (m and l["k"] == m["k"]) else ""
        o.append(f"| {l['k']:g} | {l['n_train']} | {e_tr} | "
                 f"{l['n_test']} | {e_te}{fleche} |")
    o.append("")
    return o


def principal(limite: int | None = None) -> str:
    colonnes = _colonnes(limite)
    if not colonnes:
        raise SystemExit("aucune colonne exploitable (caches vides ?)")
    DOSSIER.mkdir(exist_ok=True)
    f_in, f_out = DOSSIER / "entree.json", DOSSIER / "sortie.json"
    f_in.write_text(json.dumps({
        "colonnes": colonnes, "multiples": MULTIPLES, "rr": RR,
        "fees": FEES, "slippage": SLIPPAGE, "part_test": PART_TEST}))
    subprocess.run([str(VENV_PY), str(SCRIPT), str(f_in), str(f_out)],
                   check=True, timeout=1800)
    d = json.loads(f_out.read_text())

    horodatage = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lignes = [
        "# Balayage VectorBT — stop en multiples d'ATR (TP = 2 × stop)", "",
        f"généré le {horodatage} · {len(colonnes)} couples · "
        f"frais {FEES:.2%} + glissement {SLIPPAGE:.2%} par côté · "
        f"test = {PART_TEST:.0%} chronologique final", "",
        "> ← marque le meilleur multiple DU TRAIN — son E test en face est",
        "> le seul chiffre qui compte. Un train magnifique avec un test",
        "> négatif est du sur-apprentissage, pas une découverte. Rien ici",
        "> n'autorise une émission : le walk-forward (règle 3) reste le juge.",
        ""]
    positifs = []
    for res in d["resultats"]:
        lignes += _tableau(res)
        m = res.get("meilleur_train")
        if m and m.get("e_test") is not None and m["e_test"] > 0 \
                and m.get("n_test", 0) >= 10:
            positifs.append((res["cle"], m))
    lignes += ["## Lecture", ""]
    if positifs:
        lignes.append(f"{len(positifs)} couple(s) dont le meilleur multiple "
                      "du train reste positif sur le test :")
        for cle, m in sorted(positifs, key=lambda x: -x[1]["e_test"]):
            lignes.append(f"- **{cle}** : stop {m['k']:g} ATR → "
                          f"{m['e_test']:+.2f}R/trade sur {m['n_test']} "
                          f"trades test (train {m['e_train']:+.2f}R)")
        lignes.append("")
        lignes.append("Prochaine marche pour chacun : le walk-forward complet "
                      "(fenêtres glissantes, purge, ≥ 30 trades, ≥ 2 régimes).")
    else:
        lignes.append("**Aucun multiple ne survit au test.** Le stop n'est "
                      "pas le levier qui rend cette stratégie positive sur "
                      "ces couples — l'information vaut mieux que six mois "
                      "d'essais manuels.")
    RAPPORT.write_text("\n".join(lignes) + "\n")
    return str(RAPPORT)


if __name__ == "__main__":
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(principal(limite))
