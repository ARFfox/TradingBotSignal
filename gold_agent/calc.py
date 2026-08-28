"""Point d'entrée du calculateur : python3 -m gold_agent.calc --entree X --stop Y"""
from __future__ import annotations

import argparse
import json
import sys

from . import risk


def main() -> int:
    p = argparse.ArgumentParser(
        prog="gold_agent.calc",
        description="Calcule taille de position et R:R a partir de TES niveaux d'entree et de stop.")
    p.add_argument("--entree", type=float, required=True, help="ton prix d'entree")
    p.add_argument("--stop", type=float, required=True, help="ton stop-loss")
    p.add_argument("--capital", type=float, required=True, help="capital du compte")
    p.add_argument("--risque", type=float, default=1.0, help="risque en %% du capital (defaut 1)")
    p.add_argument("--tp", type=float, help="ton objectif, si tu en as un")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    try:
        r = risk.calculer(a.entree, a.stop, a.capital, a.risque, a.tp)
    except Exception as e:
        print(f"ECHEC: {e}", file=sys.stderr)
        return 1

    print(json.dumps(r, indent=2, ensure_ascii=False) if a.json else risk.rendre(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
