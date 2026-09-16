# Walk-forward des stratégies du skill (CRT · IFVG · ORB · POC)

*Généré le 2026-09-16 par `python3 -m research.rapport_strategies`. Ces méthodes viennent de comptes Instagram : populaires n'est pas profitables, et le corpus ne montre jamais ce qui arrive quand le setup échoue. Ce tableau est la partie qui manquait. Aucune stratégie n'émet sans verdict AUTORISÉ.*

| Stratégie · Instrument | TF | Trades | R moyen | R total | PF | Réussite | Pire creux | Fen.+ | Régimes | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| CRT · XAU/USD | H1 | 11 | -0.584 | -6.42 | 0.31 | 18.2% | -8.31 | 0/0 | range 9, tendance 2 | ❌ REFUSÉ — 11 trades < 30 · PF 0.31 ≤ 1.3 · R moyen -0.584 ≤ 0 |
| CRT · BTC/USD | H1 | 7 | -0.202 | -1.41 | 0.75 | 28.6% | -5.68 | 0/0 | range 3, tendance 4 | ❌ REFUSÉ — 7 trades < 30 · PF 0.75 ≤ 1.3 · R moyen -0.202 ≤ 0 |
| IFVG · XAU/USD | H1 | 262 | -0.209 | -54.72 | 0.75 | 21.4% | -83.15 | 12/30 | range 164, tendance 98 | ❌ REFUSÉ — PF 0.75 ≤ 1.3 · R moyen -0.209 ≤ 0 · 12/30 fenêtres évaluables positives |
| IFVG · XAU/USD | M30 | 272 | +0.152 | +41.42 | 1.2 | 28.7% | -43.65 | 12/31 | range 144, tendance 128 | ❌ REFUSÉ — PF 1.2 ≤ 1.3 · 12/31 fenêtres évaluables positives |
| IFVG · XAU/USD | M15 | 340 | -0.070 | -23.80 | 0.92 | 24.4% | -67.28 | 13/30 | range 207, tendance 133 | ❌ REFUSÉ — PF 0.92 ≤ 1.3 · R moyen -0.07 ≤ 0 · 13/30 fenêtres évaluables positives |
| IFVG · BTC/USD | H1 | 315 | -0.445 | -140.22 | 0.56 | 24.1% | -167.75 | 7/30 | range 175, tendance 140 | ❌ REFUSÉ — PF 0.56 ≤ 1.3 · R moyen -0.445 ≤ 0 · 7/30 fenêtres évaluables positives |
| IFVG · BTC/USD | M30 | 334 | -0.707 | -236.22 | 0.42 | 24.0% | -254.91 | 5/30 | range 213, tendance 121 | ❌ REFUSÉ — PF 0.42 ≤ 1.3 · R moyen -0.707 ≤ 0 · 5/30 fenêtres évaluables positives |
| IFVG · BTC/USD | M15 | 376 | -1.173 | -440.93 | 0.26 | 19.7% | -449.48 | 3/31 | range 245, tendance 131 | ❌ REFUSÉ — PF 0.26 ≤ 1.3 · R moyen -1.173 ≤ 0 · 3/31 fenêtres évaluables positives |
| ORB · XAU/USD | M15 | 16 | +0.202 | +3.22 | 1.51 | 62.5% | -4.22 | 0/0 | range 8, tendance 8 | ❌ REFUSÉ — 16 trades < 30 |
| ORB · XAU/USD | M5 | 18 | +0.290 | +5.23 | 1.84 | 66.7% | -2.19 | 0/0 | range 10, tendance 8 | ❌ REFUSÉ — 18 trades < 30 |
| POC_RETEST · XAU/USD | M30 | 54 | -0.686 | -37.07 | 0.27 | 11.1% | -37.07 | 0/8 | range 42, tendance 12 | ❌ REFUSÉ — PF 0.27 ≤ 1.3 · R moyen -0.686 ≤ 0 · 0/8 fenêtres évaluables positives |
| POC_RETEST · XAU/USD | M15 | 37 | +0.514 | +19.04 | 1.66 | 27.0% | -11.88 | 2/5 | range 27, tendance 10 | ❌ REFUSÉ — 2/5 fenêtres évaluables positives |
| POC_RETEST · BTC/USD | M30 | 104 | -0.674 | -70.14 | 0.42 | 13.5% | -72.81 | 1/19 | range 96, tendance 8 | ❌ REFUSÉ — PF 0.42 ≤ 1.3 · R moyen -0.674 ≤ 0 · 1/19 fenêtres évaluables positives |
| POC_RETEST · BTC/USD | M15 | 186 | -0.748 | -139.21 | 0.46 | 15.1% | -169.04 | 6/25 | range 174, tendance 12 | ❌ REFUSÉ — PF 0.46 ≤ 1.3 · R moyen -0.748 ≤ 0 · 6/25 fenêtres évaluables positives |

## Lecture
- Même protocole que la règle du projet : fenêtres glissantes, purge,
  coûts réels, ≥ 30 trades, ≥ 2 régimes, PF > 1,3, fenêtres évaluables.
- Un RÉFUSÉ « peu de trades » sur CRT/ORB est attendu : une occasion par
  jour au mieux — l'échantillon se construit avec l'historique.
- Sur l'or, le profil volume est un profil de TEMPS (volume absent chez
  Twelve Data) : le verdict juge cette dégradation aussi.
- ⚠️ COMPARAISONS MULTIPLES : 14 couples testés — au niveau de ces seuils,
  UN survivant peut être un coup de chance. Le seul AUTORISÉ (POC · or M15)
  repose sur ~52 jours de calendrier : il doit se reconfirmer sur les
  semaines qui viennent (relancer ce rapport) avant d'exister ailleurs
  que dans ce tableau. Un candidat n'est pas un signal.
