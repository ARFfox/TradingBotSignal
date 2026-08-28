"""Point d'entree : python3 -m gold_agent [--json] [--symbol SYM] [--bars N]"""
from __future__ import annotations

import argparse
import json
import sys

from . import analyze, report


def main() -> int:
    p = argparse.ArgumentParser(prog="gold_agent", description="Agent d'analyse de l'or via TradingView")
    p.add_argument("--symbol", default=analyze.GOLD, help="symbole TradingView (defaut: %(default)s)")
    p.add_argument("--bars", type=int, default=300, help="bougies par timeframe (max 500)")
    p.add_argument("--json", action="store_true", help="sortie JSON brute")
    p.add_argument("--no-context", action="store_true", help="ignorer le contexte macro (plus rapide)")
    p.add_argument("--m1", action="store_true",
                   help="ajoute le timeframe M1 (execution) avec detection des FVG")
    p.add_argument("--draw", action="store_true",
                   help="tracer les zones sur le graphique TradingView")
    p.add_argument("--clear-draw", action="store_true",
                   help="effacer uniquement les traces de l'agent, puis quitter")
    a = p.parse_args()

    if a.clear_draw:
        from . import draw_levels
        n = draw_levels.clear_mine()
        print(f"{n} objet(s) trace(s) par l'agent supprime(s). Tes propres traces sont intactes.")
        return 0

    try:
        rep = analyze.run(
            symbol=a.symbol,
            bars_count=a.bars,
            context_symbols=() if a.no_context else ("TVC:DXY",),
            timeframes=analyze.TIMEFRAMES_M1 if a.m1 else analyze.TIMEFRAMES,
        )
    except Exception as e:
        print(f"ECHEC: {e}", file=sys.stderr)
        return 1

    # Le dernier rapport est conserve : le calculateur de risque s'y refere
    # pour mesurer le R:R vers les niveaux reellement detectes.
    try:
        from pathlib import Path
        Path.home().joinpath(".gold_agent_last.json").write_text(
            json.dumps(rep, ensure_ascii=False))
    except Exception:
        pass

    print(json.dumps(rep, indent=2, ensure_ascii=False) if a.json else report.render(rep))

    if a.draw:
        from . import draw_levels
        try:
            res = draw_levels.draw(rep)
        except Exception as e:
            print(f"\nTrace impossible: {e}", file=sys.stderr)
            return 1
        portee = f", portee +/-{res['portee']} pts" if res.get("portee") else ""
        print(f"\n{len(res['traces'])} zone(s) tracee(s) sur TradingView "
              f"({res['nb_objets']} objets{portee})")
        if res.get("hors_portee"):
            print(f"  {res['hors_portee']} niveau(x) ecarte(s) : trop loin pour l'echelle "
                  f"du timeframe d'execution (visibles sans --m1)")
        for t in res["traces"]:
            if t["genre"] == "invalidation":
                print(f"  INVALIDATION {t['prix']:.2f} — {t['sens']}")
            else:
                print(f"  {t['genre']:<11} {t['timeframe']:<3} {t['prix']:>9.2f}  "
                      f"zone {t['zone'][0]}–{t['zone'][1]}  ({t['touches']} touches)")
        print("\n  Retirer ces traces : python3 -m gold_agent --clear-draw")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
