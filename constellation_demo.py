#!/usr/bin/env python3
"""Demonstration executable d'AG-09/AG-10 — extraite de constellation_agent.py
(regle 17 : aucun fichier > 500 lignes). Le module de production ne bouge pas.

    python3 constellation_demo.py             # pivot = or
    python3 constellation_demo.py BTC-USD     # pivot = bitcoin
"""
from __future__ import annotations

import pandas as pd

from constellation_agent import (CACHE, Constellation, Miroir, NOMS,
                                 biais_provisoire)


def _demo(pivot: str, prix: pd.DataFrame) -> None:
    n = lambda t: NOMS.get(t, t)
    ag = Constellation(prix, cache=CACHE)
    g = ag.groupes(pivot)

    print(f"\n{'=' * 78}\n  CONSTELLATION DE {n(pivot).upper()}\n{'=' * 78}")
    for cle, titre in (("satellites", "SATELLITES — memes mouvements"),
                       ("miroirs", "MIROIRS — mouvements opposes")):
        print(f"\n  {titre}")
        if not g[cle]:
            print("    (aucun)")
        for m in g[cle]:
            t = f"  [{m.tendance}]" if m.tendance != "-" else ""
            print(f"    {n(m.ticker):<24} corr {m.corr:+.2f}  "
                  f"poids {m.poids:.2f}{t}")
    print(f"\n  DECOUPLES : {len(g['decouples'])} actifs sans relation exploitable")

    biais = biais_provisoire(prix)
    print(f"\n{'=' * 78}\n  VERDICT INTERMARCHE — biais actuels (moyennes 20/50 j)\n{'=' * 78}")
    for m in g["satellites"] + g["miroirs"]:
        print(f"    {n(m.ticker):<24} {biais.get(m.ticker, 'inconnu')}")

    mi = Miroir(ag)
    print()
    for sens in ("achat", "vente"):
        conf, s = mi.appliquer(pivot, sens, 0.65, biais)
        fleche = "ACHAT " if sens == "achat" else "VENTE "
        print(f"  Hypothese {fleche}{n(pivot)} a 0,65 de confiance")
        print(f"    -> {conf}   {s.resume()}")
        if s.confirment:
            print(f"       confirment  : {', '.join(n(x) for x in s.confirment)}")
        if s.contredisent:
            print(f"       contredisent: {', '.join(n(x) for x in s.contredisent)}")
        print()

    if ag.ruptures():
        print(f"{'=' * 78}\n  RUPTURES DE REGIME depuis le dernier calcul\n{'=' * 78}")
        for r in ag.ruptures():
            print(f"    {n(r['actif']):<24} {r['type']:<10} "
                  f"{r['avant']:+.2f} -> {r['apres']:+.2f}")
    ag.sauver()
    print("  (correlations mises en cache — les ruptures apparaitront au "
          "prochain lancement)\n")



def principal() -> None:
    import sys, warnings
    warnings.filterwarnings("ignore")
    pivot = next((a for a in sys.argv[1:] if not a.startswith("-")), "GC=F")
    if pivot not in NOMS:
        print(f"Pivot inconnu : {pivot}\nDisponibles : {', '.join(NOMS)}")
        sys.exit(1)
    try:
        import yfinance as yf
    except ImportError:
        print("pip3 install yfinance pandas numpy")
        sys.exit(1)
    print(f"Telechargement de {len(NOMS)} actifs (3 ans, quotidien)...")
    d = yf.download(list(NOMS), period="3y", interval="1d",
                    progress=False, auto_adjust=True)["Close"]
    d = d.dropna(axis=1, how="all")
    print(f"OK — {len(d)} lignes, derniere donnee : {d.index[-1].date()}")
    if pivot not in d.columns:
        print(f"Pas de donnees pour {pivot}.")
        sys.exit(1)
    _demo(pivot, d)


if __name__ == "__main__":
    principal()
