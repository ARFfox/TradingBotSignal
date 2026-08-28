"""Setup courant de la règle : python3 -m gold_agent.setup --tf 60 --draw"""
from __future__ import annotations

import argparse
import json
import sys

from . import bridge, draw_levels, strategy as sg

TF_SEC = {"D": 86400, "240": 14400, "60": 3600, "30": 1800, "15": 900, "5": 300, "1": 60}
PRESETS = {
    "D": dict(ema_fast=20, ema_slow=50, pivot_span=3),
    "240": dict(ema_fast=50, ema_slow=200, pivot_span=3),
    "60": dict(ema_fast=20, ema_slow=50, pivot_span=3),
    "30": dict(ema_fast=20, ema_slow=50, pivot_span=3),
    "15": dict(ema_fast=20, ema_slow=50, pivot_span=3),
    "5": dict(ema_fast=20, ema_slow=50, pivot_span=2),
    "1": dict(ema_fast=20, ema_slow=50, pivot_span=2),
}


def main() -> int:
    p = argparse.ArgumentParser(prog="gold_agent.setup",
                                description="Niveaux produits par la regle mecanique, tels quels.")
    p.add_argument("--tf", default="60", help="timeframe (D, 240, 60, 15, 5, 1)")
    p.add_argument("--symbol", default="FOREXCOM:XAUUSD")
    p.add_argument("--rr-min", type=float, default=1.5)
    p.add_argument("--k-stop", type=float, default=1.5)
    p.add_argument("--sens", default="les_deux", choices=["achat", "vente", "les_deux"])
    p.add_argument("--rsi-max-achat", type=float, default=70.0,
                   help="ne pas acheter au-dessus de ce RSI (defaut 70 ; 100 = desactive)")
    p.add_argument("--rsi-min-vente", type=float, default=30.0,
                   help="ne pas vendre en dessous de ce RSI (defaut 30 ; 0 = desactive)")
    p.add_argument("--mtf", type=int, default=0,
                   help="filtre timeframe superieur : nb de bougies agregees (0 = desactive)")
    p.add_argument("--draw", action="store_true", help="tracer les zones sur TradingView")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    params = sg.Params(rr_min=a.rr_min, k_stop=a.k_stop, sens=a.sens,
                       rsi_max_achat=a.rsi_max_achat, rsi_min_vente=a.rsi_min_vente,
                       facteur_superieur=a.mtf, **PRESETS.get(a.tf, PRESETS["60"]))

    try:
        bridge.ensure_tradingview()
        bridge.set_symbol(a.symbol)
        bridge.set_timeframe(a.tf)
        bars = bridge.ohlcv(300)
    except Exception as e:
        print(f"ECHEC: {e}", file=sys.stderr)
        return 1

    s = sg.setup_actuel(bars, params)

    if a.json:
        print(json.dumps(s, indent=2, ensure_ascii=False))
    elif not s.get("setup"):
        print(f"Aucun setup en {a.tf} : {s['raison']}")
        print("La regle ne se declenche pas. C'est une sortie valide, pas une erreur.")
        return 0
    else:
        etat = "DECLENCHE — le prix est dans la zone" if s["declenche"] \
            else f"EN ATTENTE — le prix est a {s['distance_a_entree']} pts de la zone"
        print("=" * 66)
        print(f"  SETUP {s['setup'].upper()} — {a.symbol} en {a.tf}")
        print(f"  {etat}")
        print("=" * 66)
        print(f"\n  Prix actuel {s['prix_actuel']}   ATR {s['atr']}   RSI {s['rsi']}"
              f"   ecart EMA {s['ecart_ema_pct']:+.2f}%\n")
        print(f"  ENTREE    {s['entree']:>9.2f}   zone {s['entree_zone']}")
        print(f"  STOP      {s['stop']:>9.2f}   zone {s['stop_zone']}   risque {s['risque_pts']} pts")
        print(f"  OBJECTIF  {s['objectif']:>9.2f}   zone {s['objectif_zone']}   gain {s['gain_pts']} pts")
        print(f"\n  R:R {s['rr']}" + ("" if s["rr_suffisant"] else f"  (SOUS le minimum de {a.rr_min})"))
        print("\n  Sortie mecanique de la regle, pas une recommandation.")
        print(f"  Ce que la regle vaut : python3 -m gold_agent.backtest --tf {a.tf}")
        print("=" * 66)

    if a.draw and s.get("setup"):
        res = draw_levels.draw_setup(s, bars[-1]["time"], TF_SEC.get(a.tf, 3600))
        print(f"\n  {len(res['traces'])} zone(s) tracee(s) ({res['nb_objets']} objets)")
        print("  Retirer : python3 -m gold_agent --clear-draw")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
