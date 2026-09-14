# Walk-forward des stratégies du skill (CRT · IFVG · ORB · POC)

*Généré le 2026-09-14 par `python3 -m research.rapport_strategies`. Ces méthodes viennent de comptes Instagram : populaires n'est pas profitables, et le corpus ne montre jamais ce qui arrive quand le setup échoue. Ce tableau est la partie qui manquait. Aucune stratégie n'émet sans verdict AUTORISÉ.*

| Stratégie · Instrument | TF | Trades | R moyen | R total | PF | Réussite | Pire creux | Fen.+ | Régimes | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| CRT · XAU/USD | H1 | 11 | -0.584 | -6.42 | 0.31 | 18.2% | -8.31 | 0/0 | range 9, tendance 2 | ❌ REFUSÉ — 11 trades < 30 · PF 0.31 ≤ 1.3 · R moyen -0.584 ≤ 0 |
| CRT · BTC/USD | H1 | 8 | -0.317 | -2.54 | 0.63 | 25.0% | -6.81 | 0/0 | range 3, tendance 5 | ❌ REFUSÉ — 8 trades < 30 · PF 0.63 ≤ 1.3 · R moyen -0.317 ≤ 0 |
| IFVG · XAU/USD | H1 | 256 | -0.219 | -56.13 | 0.74 | 21.5% | -84.94 | 10/29 | range 156, tendance 100 | ❌ REFUSÉ — PF 0.74 ≤ 1.3 · R moyen -0.219 ≤ 0 · 10/29 fenêtres évaluables positives |
| IFVG · XAU/USD | M30 | 270 | +0.157 | +42.47 | 1.2 | 28.9% | -34.22 | 12/30 | range 137, tendance 133 | ❌ REFUSÉ — PF 1.2 ≤ 1.3 · 12/30 fenêtres évaluables positives |
| IFVG · XAU/USD | M15 | 335 | -0.075 | -25.10 | 0.91 | 25.7% | -54.80 | 14/27 | range 206, tendance 129 | ❌ REFUSÉ — PF 0.91 ≤ 1.3 · R moyen -0.075 ≤ 0 |
| IFVG · BTC/USD | H1 | 310 | -0.455 | -141.17 | 0.54 | 24.8% | -163.64 | 5/31 | range 172, tendance 138 | ❌ REFUSÉ — PF 0.54 ≤ 1.3 · R moyen -0.455 ≤ 0 · 5/31 fenêtres évaluables positives |
| IFVG · BTC/USD | M30 | 329 | -0.661 | -217.44 | 0.45 | 24.9% | -254.79 | 7/31 | range 199, tendance 130 | ❌ REFUSÉ — PF 0.45 ≤ 1.3 · R moyen -0.661 ≤ 0 · 7/31 fenêtres évaluables positives |
| IFVG · BTC/USD | M15 | 362 | -1.224 | -443.05 | 0.24 | 18.8% | -449.57 | 2/29 | range 234, tendance 128 | ❌ REFUSÉ — PF 0.24 ≤ 1.3 · R moyen -1.224 ≤ 0 · 2/29 fenêtres évaluables positives |
| ORB · XAU/USD | M15 | 17 | +0.244 | +4.15 | 1.66 | 64.7% | -4.22 | 0/0 | range 9, tendance 8 | ❌ REFUSÉ — 17 trades < 30 |
| ORB · XAU/USD | M5 | 16 | +0.084 | +1.35 | 1.19 | 56.2% | -2.19 | 0/0 | range 9, tendance 7 | ❌ REFUSÉ — 16 trades < 30 · PF 1.19 ≤ 1.3 |
| POC_RETEST · XAU/USD | M30 | 52 | -0.465 | -24.17 | 0.47 | 17.3% | -29.09 | 1/6 | range 42, tendance 10 | ❌ REFUSÉ — PF 0.47 ≤ 1.3 · R moyen -0.465 ≤ 0 · 1/6 fenêtres évaluables positives |
| POC_RETEST · XAU/USD | M15 | 33 | +0.767 | +25.32 | 1.99 | 27.3% | -11.81 | 2/3 | range 23, tendance 10 | ✅ AUTORISÉ — tous les critères passés · ⚠️ preuve courte : 52 j de calendrier — et 14 candidats testés : un faux positif est statistiquement attendu. À reconfirmer hors échantillon avant toute question d'émission. |
| POC_RETEST · BTC/USD | M30 | 117 | -0.659 | -77.07 | 0.44 | 12.8% | -82.70 | 4/24 | range 110, tendance 7 | ❌ REFUSÉ — PF 0.44 ≤ 1.3 · R moyen -0.659 ≤ 0 · 4/24 fenêtres évaluables positives |
| POC_RETEST · BTC/USD | M15 | 168 | -0.618 | -103.80 | 0.53 | 19.6% | -127.91 | 8/24 | range 158, tendance 10 | ❌ REFUSÉ — PF 0.53 ≤ 1.3 · R moyen -0.618 ≤ 0 · 8/24 fenêtres évaluables positives |

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
