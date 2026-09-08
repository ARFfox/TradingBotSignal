# Rapport d'edge — walk-forward multi-marchés

*Généré le 2026-09-08 par `python3 -m research.rapport_edge` — fenêtres glissantes, purge 5 bougies, coûts par instrument (registre), paramètres mesurés du projet, aucune optimisation dans la boucle. Une fenêtre ne vote qu'à partir de 3 trades résolus.*

| Instrument | TF | Trades | R moyen | R total | PF | Réussite | Pire creux | Fen.+ | Régimes | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| XAU/USD | H4 | 39 | +0.621 | +24.21 | 2.5 | 59.0% | -7.06 | 3/3 | range 24, tendance 15 | ✅ AUTORISÉ — tous les critères passés |
| XAU/USD | H1 | 36 | +0.297 | +10.68 | 1.52 | 44.4% | -11.20 | 3/4 | range 20, tendance 16 | ✅ AUTORISÉ — tous les critères passés |
| XAU/USD | M30 | 88 | +0.302 | +26.61 | 1.54 | 45.5% | -10.37 | 9/16 | range 54, tendance 34 | ✅ AUTORISÉ — tous les critères passés |
| XAU/USD | M15 | 84 | +0.092 | +7.69 | 1.14 | 38.1% | -29.01 | 3/13 | range 51, tendance 33 | ❌ REFUSÉ — PF 1.14 ≤ 1.3 · 3/13 fenêtres évaluables positives |
| XAU/USD | M5 | 67 | +0.346 | +23.15 | 1.57 | 44.8% | -14.54 | 9/14 | range 36, tendance 31 | ✅ AUTORISÉ — tous les critères passés |
| BTC/USD | H4 | 23 | -0.439 | -10.10 | 0.45 | 21.7% | -11.70 | 0/1 | range 9, tendance 14 | ❌ REFUSÉ — 23 trades < 30 · PF 0.45 ≤ 1.3 · R moyen -0.439 ≤ 0 · 0/1 fenêtres évaluables positives |
| BTC/USD | H1 | 19 | -0.150 | -2.85 | 0.81 | 26.3% | -10.34 | 0/0 | range 8, tendance 11 | ❌ REFUSÉ — 19 trades < 30 · PF 0.81 ≤ 1.3 · R moyen -0.15 ≤ 0 |
| BTC/USD | M30 | 73 | +0.095 | +6.96 | 1.15 | 45.2% | -13.27 | 6/13 | range 45, tendance 28 | ❌ REFUSÉ — PF 1.15 ≤ 1.3 · 6/13 fenêtres évaluables positives |
| BTC/USD | M15 | 98 | -0.264 | -25.83 | 0.69 | 36.7% | -35.82 | 6/18 | range 50, tendance 48 | ❌ REFUSÉ — PF 0.69 ≤ 1.3 · R moyen -0.264 ≤ 0 · 6/18 fenêtres évaluables positives |
| BTC/USD | M5 | 79 | -0.588 | -46.43 | 0.45 | 31.6% | -59.45 | 3/15 | range 38, tendance 41 | ❌ REFUSÉ — PF 0.45 ≤ 1.3 · R moyen -0.588 ≤ 0 · 3/15 fenêtres évaluables positives |
| ETH/USD | H4 | 28 | +0.413 | +11.57 | 1.87 | 53.6% | -4.10 | 2/2 | range 16, tendance 12 | ❌ REFUSÉ — 28 trades < 30 |
| ETH/USD | H1 | 14 | +0.676 | +9.47 | 2.28 | 50.0% | -3.18 | 1/1 | range 6, tendance 8 | ❌ REFUSÉ — 14 trades < 30 |
| ETH/USD | M30 | 70 | +0.018 | +1.24 | 1.03 | 41.4% | -18.22 | 5/14 | range 42, tendance 28 | ❌ REFUSÉ — PF 1.03 ≤ 1.3 · 5/14 fenêtres évaluables positives |
| ETH/USD | M15 | 67 | -0.243 | -16.29 | 0.71 | 35.8% | -20.01 | 3/12 | range 37, tendance 30 | ❌ REFUSÉ — PF 0.71 ≤ 1.3 · R moyen -0.243 ≤ 0 · 3/12 fenêtres évaluables positives |
| ETH/USD | M5 | 48 | -0.460 | -22.10 | 0.54 | 37.5% | -24.94 | 3/9 | range 28, tendance 20 | ❌ REFUSÉ — PF 0.54 ≤ 1.3 · R moyen -0.46 ≤ 0 · 3/9 fenêtres évaluables positives |
| EUR/USD | H1 | 23 | -0.055 | -1.26 | 0.0 | 0.0% | -1.26 | 0/1 | range 9, tendance 14 | ❌ REFUSÉ — 23 trades < 30 · PF 0.0 ≤ 1.3 · R moyen -0.055 ≤ 0 · 0/1 fenêtres évaluables positives |
| EUR/USD | M30 | 0 | +0.000 | +0.00 | 0.0 | 0.0% | +0.00 | 0/0 |  | ❌ REFUSÉ — 0 trades < 30 · 0 régime(s) couvert(s) < 2 · PF 0.0 ≤ 1.3 · R moyen 0.0 ≤ 0 |
| EUR/USD | M15 | 0 | +0.000 | +0.00 | 0.0 | 0.0% | +0.00 | 0/0 |  | ❌ REFUSÉ — 0 trades < 30 · 0 régime(s) couvert(s) < 2 · PF 0.0 ≤ 1.3 · R moyen 0.0 ≤ 0 |
| EUR/USD | M5 | 2 | -1.012 | -2.02 | 0.0 | 0.0% | -2.02 | 0/0 | range 2 | ❌ REFUSÉ — 2 trades < 30 · 1 régime(s) couvert(s) < 2 · PF 0.0 ≤ 1.3 · R moyen -1.012 ≤ 0 |
| SPY | H1 | 35 | -0.415 | -14.54 | 0.48 | 22.9% | -23.77 | 0/5 | range 13, tendance 22 | ❌ REFUSÉ — PF 0.48 ≤ 1.3 · R moyen -0.415 ≤ 0 · 0/5 fenêtres évaluables positives |
| SPY | M30 | 14 | +0.016 | +0.23 | 1.02 | 35.7% | -3.37 | 1/2 | range 7, tendance 7 | ❌ REFUSÉ — 14 trades < 30 · PF 1.02 ≤ 1.3 |
| SPY | M15 | 21 | -0.425 | -8.92 | 0.52 | 23.8% | -12.09 | 1/4 | range 14, tendance 7 | ❌ REFUSÉ — 21 trades < 30 · PF 0.52 ≤ 1.3 · R moyen -0.425 ≤ 0 · 1/4 fenêtres évaluables positives |
| SPY | M5 | 58 | -0.238 | -13.81 | 0.71 | 34.5% | -14.49 | 5/9 | range 18, tendance 40 | ❌ REFUSÉ — PF 0.71 ≤ 1.3 · R moyen -0.238 ≤ 0 |

## Réserves
- **XAU/USD M5** : ⚠️ preuve courte : 17 j de calendrier — critères passés mais conditions de marché peu variées

## Lecture
- Verdict CUMULATIF : ≥ 30 trades ET ≥ 2 régimes ET PF > 1,3 ET R moyen > 0 ET
  ≥ 50 % des fenêtres évaluables positives. Un critère manquant → REFUSÉ.
- Les coûts viennent du registre (`Instrument.cout_pct`) — estimations
  prudentes à affiner par mesure sur le compte réel.
- Un REFUSÉ « échantillon court / fenêtres » n'est pas un échec de la règle :
  c'est une preuve qui manque encore. Le couple reste observé et testé.
