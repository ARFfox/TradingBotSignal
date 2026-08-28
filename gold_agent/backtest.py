"""Backtest de la règle : python3 -m gold_agent.backtest --tf 60"""
from __future__ import annotations

import argparse
import json
import sys

from . import bridge, datasource as ds, strategy as sg

TF_NOMS = {"D": "Daily", "240": "H4", "60": "H1", "30": "M30", "15": "M15", "5": "M5", "1": "M1"}
PRESETS = {
    "D": dict(ema_fast=20, ema_slow=50, delai_max=30),
    "240": dict(ema_fast=50, ema_slow=200, delai_max=40),
    "60": dict(ema_fast=20, ema_slow=50, delai_max=40),
    "30": dict(ema_fast=20, ema_slow=50, delai_max=40),
    "15": dict(ema_fast=20, ema_slow=50, delai_max=40),
    "5": dict(ema_fast=20, ema_slow=50, delai_max=60),
    "1": dict(ema_fast=20, ema_slow=50, delai_max=60),
}


def main() -> int:
    p = argparse.ArgumentParser(prog="gold_agent.backtest",
                                description="Mesure ce que la regle a produit sur l'historique.")
    p.add_argument("--tf", default="60", help="timeframe TradingView (D, 240, 60, 15, 5, 1)")
    p.add_argument("--symbol", default="FOREXCOM:XAUUSD")
    p.add_argument("--bars", type=int, default=500)
    p.add_argument("--source", default="tradingview", choices=["tradingview", "twelvedata"],
                   help="tradingview = 300 bougies max ; twelvedata = jusqu'a 5000 (cle requise)")
    p.add_argument("--sens", default="les_deux", choices=["achat", "vente", "les_deux"])
    p.add_argument("--rsi-max-achat", type=float, default=70.0,
                   help="ne pas acheter au-dessus de ce RSI (defaut 70 ; 100 = desactive)")
    p.add_argument("--rsi-min-vente", type=float, default=30.0,
                   help="ne pas vendre en dessous de ce RSI (defaut 30 ; 0 = desactive)")
    p.add_argument("--mtf", type=int, default=0,
                   help="filtre timeframe superieur : nb de bougies agregees (0 = desactive)")
    p.add_argument("--rr-min", type=float, default=1.5, help="R:R minimum exige (defaut 1.5)")
    p.add_argument("--k-stop", type=float, default=1.5, help="stop en multiples d'ATR (defaut 1.5)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    params = sg.Params(sens=a.sens, rr_min=a.rr_min, k_stop=a.k_stop,
                       rsi_max_achat=a.rsi_max_achat, rsi_min_vente=a.rsi_min_vente,
                       facteur_superieur=a.mtf,
                       **PRESETS.get(a.tf, PRESETS["60"]))

    try:
        if a.source == "twelvedata":
            sym = a.symbol.split(":")[-1]
            if sym.upper() in ("XAUUSD", "GOLD"):
                sym = "XAU/USD"
            bars = ds.twelvedata_bars(sym, a.tf, a.bars)
        else:
            bridge.ensure_tradingview()
            bridge.set_symbol(a.symbol)
            bridge.set_timeframe(a.tf)
            bars = bridge.ohlcv(a.bars)
    except Exception as e:
        print(f"ECHEC: {e}", file=sys.stderr)
        return 1

    if len(bars) < 250:
        print(f"  Attention : seulement {len(bars)} bougies — echantillon trop court "
              f"pour conclure quoi que ce soit.\n")

    sigs = sg.detecter(bars, params)
    trades = sg.simuler(bars, sigs, params)
    stats = sg.statistiques(trades)

    sortie = {
        "symbole": a.symbol, "timeframe": TF_NOMS.get(a.tf, a.tf),
        "bougies": len(bars), "signaux_bruts": len(sigs),
        "parametres": {"ema": [params.ema_fast, params.ema_slow], "k_stop": params.k_stop,
                       "rr_min": params.rr_min, "delai_max": params.delai_max, "sens": params.sens},
        "statistiques": stats,
        "trades": [{"sens": t.signal.sens, "entree": t.signal.entree, "stop": t.signal.stop,
                    "objectif": t.signal.objectif, "rr_prevu": t.signal.rr,
                    "resultat": t.resultat, "r_obtenu": t.r_multiple,
                    "bougies": t.bougies_tenues} for t in trades],
    }

    if a.json:
        print(json.dumps(sortie, indent=2, ensure_ascii=False))
        return 0

    L = ["=" * 68,
         f"  BACKTEST — {a.symbol} en {TF_NOMS.get(a.tf, a.tf)}  (source: {a.source})",
         f"  Regle : repli sur niveau confirme en tendance",
         f"  EMA{params.ema_fast}/{params.ema_slow}  stop {params.k_stop}xATR  "
         f"R:R min {params.rr_min}  delai {params.delai_max} bougies",
         "=" * 68, "",
         f"  {len(bars)} bougies analysees, {len(sigs)} signaux bruts, "
         f"{stats.get('trades', 0)} trades distincts", ""]

    if stats.get("trades"):
        L.append(f"  {stats['fiabilite']}")
        L.append("")
        for cle, libelle in (
            ("trades", "Trades"), ("gagnants", "Objectif atteint"),
            ("perdants", "Stop touche"), ("expires", "Sortis par delai"),
            ("taux_objectif_atteint_pct", "Taux objectif atteint (%)"),
            ("taux_profitable_pct", "Taux profitable (%)"),
            ("esperance_R", "Esperance (R par trade)"),
            ("total_R", "Cumul (R)"), ("facteur_profit", "Facteur de profit"),
            ("pire_serie_pertes", "Pire serie de pertes"),
            ("pire_creux_R", "Pire creux cumule (R)"),
            ("duree_moyenne_bougies", "Duree moyenne (bougies)"),
        ):
            L.append(f"    {libelle:<28} {stats.get(cle)}")
        L += ["", "  DETAIL DES TRADES", ""]
        for t in trades:
            s = t.signal
            L.append(f"    {s.sens:<6} entree {s.entree:>9.2f}  stop {s.stop:>9.2f}  "
                     f"obj {s.objectif:>9.2f}  RR prevu {s.rr:>5.2f}  ->  "
                     f"{t.resultat:<8} {t.r_multiple:+6.2f}R  ({t.bougies_tenues} bougies)")
    else:
        L.append(f"  {stats.get('verdict')}")

    L += ["", "-" * 68,
          "  Un R = le risque d'un trade. +2R = deux fois le montant risque.",
          "  Resultats hors spread, commissions et glissement — la realite sera",
          "  moins bonne. Les performances passees ne predisent rien.",
          "=" * 68]
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
