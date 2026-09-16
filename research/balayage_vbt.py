"""Balayage VectorBT (CHANTIER #11) — s'exécute dans .venv-recherche.

Script AUTONOME (numpy/pandas/vectorbt seulement) : il reçoit un JSON de
colonnes {close, atr_frac, entrées par sens}, balaye les multiples d'ATR du
stop (TP = rr × stop), et rend pour chaque valeur l'espérance en R sur le
TRAIN et sur le TEST (découpe chronologique — jamais l'inverse).

Règles du SKILL §2, câblées :
- fees et slippage sont des paramètres, pas des options ;
- on CHERCHE sur le train, on JUGE une fois sur le test ; le meilleur
  affiché est le meilleur DU TRAIN, avec son résultat test en face —
  c'est le protocole de parametres_agents, pas un concours de backtests.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd


def _esperance_r(pf, rr: float, cout_r: float) -> tuple[int, float | None]:
    """(nb trades, espérance en R) : chaque trade sort à −1R ou +rr R
    (stops/TP en fractions fixes), moins les coûts convertis en R."""
    n = int(pf.trades.count())
    if n == 0:
        return 0, None
    taux = float(pf.trades.win_rate())
    return n, taux * rr - (1 - taux) - cout_r


def _passer(close: pd.Series, entrees: pd.Series, sl_frac: pd.Series,
            sens: str, rr: float, fees: float, slippage: float):
    # vectorbt n'existe QUE dans .venv-recherche (numba absent du 3.14) :
    # l'import vit ici pour que l'env principal puisse charger le module.
    import vectorbt as vbt
    return vbt.Portfolio.from_signals(
        close, entries=entrees, exits=None,
        sl_stop=sl_frac.values, tp_stop=(rr * sl_frac).values,
        direction="longonly" if sens == "achat" else "shortonly",
        fees=fees, slippage=slippage, freq="1min")


def balayer(colonne: dict, multiples: list[float], rr: float,
            fees: float, slippage: float, part_test: float) -> dict:
    close = pd.Series(colonne["close"], dtype=float)
    atr_frac = pd.Series(colonne["atr_frac"], dtype=float).fillna(0.0)
    n = len(close)
    coupe = int(n * (1 - part_test))
    lignes = []
    for k in multiples:
        sl_frac = (k * atr_frac).clip(lower=1e-6)
        cout_r_moy = []
        n_tr, e_tr, n_te, e_te = 0, [], 0, []
        for sens in ("achat", "vente"):
            idx = [i for i in colonne.get(sens + "s", [])]
            if not idx:
                continue
            entrees = pd.Series(False, index=close.index)
            entrees.iloc[[i for i in idx if i < n]] = True
            frais_r = 2 * (fees + slippage) / max(1e-6, float(
                sl_frac.iloc[[i for i in idx if i < n]].mean()))
            for debut, fin, accumulateur in ((0, coupe, "train"),
                                             (coupe, n, "test")):
                pf = _passer(close.iloc[debut:fin],
                             entrees.iloc[debut:fin],
                             sl_frac.iloc[debut:fin],
                             sens, rr, fees, slippage)
                nb, e = _esperance_r(pf, rr, frais_r)
                if e is None:
                    continue
                if accumulateur == "train":
                    n_tr += nb
                    e_tr.append((nb, e))
                else:
                    n_te += nb
                    e_te.append((nb, e))
            cout_r_moy.append(frais_r)

        def _moy(paires):
            total = sum(nb for nb, _ in paires)
            return (sum(nb * e for nb, e in paires) / total) if total else None
        lignes.append({"k": k, "n_train": n_tr, "e_train": _moy(e_tr),
                       "n_test": n_te, "e_test": _moy(e_te),
                       "cout_r": round(float(np.mean(cout_r_moy)), 3)
                       if cout_r_moy else None})

    exploitables = [l for l in lignes if l["e_train"] is not None]
    meilleur = (max(exploitables, key=lambda l: l["e_train"])
                if exploitables else None)
    return {"cle": colonne["cle"], "lignes": lignes, "meilleur_train": meilleur}


def main() -> None:
    entree, sortie = sys.argv[1], sys.argv[2]
    d = json.loads(open(entree).read())
    out = [balayer(c, d["multiples"], d["rr"], d["fees"], d["slippage"],
                   d["part_test"]) for c in d["colonnes"]]
    with open(sortie, "w") as f:
        json.dump({"resultats": out, "parametres": {
            "multiples": d["multiples"], "rr": d["rr"], "fees": d["fees"],
            "slippage": d["slippage"], "part_test": d["part_test"]}}, f)


if __name__ == "__main__":
    main()
