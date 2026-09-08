# Rapport d'edge — walk-forward XAU/USD

*Généré le 2026-09-08 par `python3 -m research.rapport_edge` — fenêtres glissantes, purge 5 bougies, coût 0,3 pt/trade, paramètres mesurés du projet (aucune optimisation dans la boucle). Une fenêtre ne vote qu'à partir de 3 trades résolus.*

| Instrument | TF | Trades | R moyen | R total | PF | Réussite | Pire creux | Fen.+ | Régimes | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| XAU/USD | H4 | 39 | +0.621 | +24.21 | 2.5 | 59.0% | -7.06 | 3/3 | range 24, tendance 15 | ✅ AUTORISÉ — tous les critères passés |
| XAU/USD | H1 | 36 | +0.297 | +10.68 | 1.52 | 44.4% | -11.20 | 3/4 | range 20, tendance 16 | ✅ AUTORISÉ — tous les critères passés |
| XAU/USD | M30 | 88 | +0.271 | +23.82 | 1.47 | 44.3% | -11.34 | 9/16 | range 55, tendance 33 | ✅ AUTORISÉ — tous les critères passés |
| XAU/USD | M15 | 82 | +0.009 | +0.78 | 1.01 | 35.4% | -34.12 | 3/13 | range 49, tendance 33 | ❌ REFUSÉ — PF 1.01 ≤ 1.3 · 3/13 fenêtres évaluables positives |
| XAU/USD | M5 | 69 | +0.331 | +22.83 | 1.55 | 44.9% | -14.54 | 8/13 | range 36, tendance 33 | ✅ AUTORISÉ — tous les critères passés |

## Réserves
- **M5** : ⚠️ preuve courte : 17 j de calendrier seulement — critères passés mais conditions de marché peu variées

## Lecture
- Verdict CUMULATIF : ≥ 30 trades ET ≥ 2 régimes ET PF > 1,3 ET R moyen > 0 ET
  ≥ 50 % des fenêtres évaluables positives. Un critère manquant → REFUSÉ.
- Un REFUSÉ « échantillon court / fenêtres » n'est pas un échec de la règle :
  c'est une preuve qui manque encore. Le couple reste observé et testé.
- Les autres instruments (BTC, EUR/USD, SPY…) attendent leurs adapters intraday
  (phase 3) : le protocole les recevra tel quel.
