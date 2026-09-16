# Balayage VectorBT — stop en multiples d'ATR (TP = 2 × stop)

généré le 2026-09-16 17:04 UTC · 6 couples · frais 0.05% + glissement 0.02% par côté · test = 30% chronologique final

> ← marque le meilleur multiple DU TRAIN — son E test en face est
> le seul chiffre qui compte. Un train magnifique avec un test
> négatif est du sur-apprentissage, pas une découverte. Rien ici
> n'autorise une émission : le walk-forward (règle 3) reste le juge.

### BTC/USD|M30

| stop (×ATR) | n train | E train (R) | n test | E test (R) |
|---|---:|---:|---:|---:|
| 1 | 11 | -0.89 | 3 | -0.46 |
| 1.25 | 10 | -0.74 | 3 | -0.37 |
| 1.5 | 10 | -0.38 | 3 | -0.31 |
| 1.75 | 9 | -0.25 | 3 | +0.73 |
| 2 | 9 | -0.22 | 3 | +0.77 |
| 2.5 | 8 | -0.06 | 3 | -0.19 |
| 3 | 7 | +0.13 | 3 | -0.15 ← |

### BTC/USD|M15

| stop (×ATR) | n train | E train (R) | n test | E test (R) |
|---|---:|---:|---:|---:|
| 1 | 5 | -0.91 | 1 | +1.41 |
| 1.25 | 5 | -0.81 | 1 | -1.47 |
| 1.5 | 5 | -0.74 | 1 | -1.39 |
| 1.75 | 5 | -0.69 | 1 | -1.34 |
| 2 | 5 | -0.65 | 1 | +1.70 |
| 2.5 | 4 | -0.46 | 1 | +1.76 |
| 3 | 4 | -0.42 | 1 | +1.80 ← |

### ETH/USD|M30

| stop (×ATR) | n train | E train (R) | n test | E test (R) |
|---|---:|---:|---:|---:|
| 1 | 8 | -0.56 | 1 | -1.22 |
| 1.25 | 8 | -0.50 | 1 | -1.17 |
| 1.5 | 8 | -0.83 | 1 | -1.14 |
| 1.75 | 8 | -0.43 | 1 | -1.12 ← |
| 2 | 7 | -0.73 | 1 | -1.11 |
| 2.5 | 7 | -0.70 | 1 | -1.09 |
| 3 | 5 | -0.51 | 1 | -1.07 |

### ETH/USD|M15

| stop (×ATR) | n train | E train (R) | n test | E test (R) |
|---|---:|---:|---:|---:|
| 1 | 4 | -1.40 | 2 | -1.31 |
| 1.25 | 4 | -1.32 | 2 | -1.25 |
| 1.5 | 4 | -1.26 | 2 | -1.20 |
| 1.75 | 4 | -1.23 | 2 | -1.18 |
| 2 | 4 | -1.20 | 2 | -1.15 |
| 2.5 | 4 | -1.16 | 2 | -1.12 |
| 3 | 4 | -1.13 | 2 | -1.10 ← |

### SOL/USD|M30

| stop (×ATR) | n train | E train (R) | n test | E test (R) |
|---|---:|---:|---:|---:|
| 1 | 13 | -0.35 | 0 | — |
| 1.25 | 13 | -0.30 | 0 | — |
| 1.5 | 13 | -0.26 | 0 | — |
| 1.75 | 13 | -0.00 | 0 | — |
| 2 | 12 | +0.11 | 0 | — |
| 2.5 | 11 | +0.26 | 0 | — ← |
| 3 | 10 | +0.11 | 0 | — |

### SOL/USD|M15

| stop (×ATR) | n train | E train (R) | n test | E test (R) |
|---|---:|---:|---:|---:|
| 1 | 10 | -0.37 | 0 | — |
| 1.25 | 9 | -0.22 | 0 | — |
| 1.5 | 9 | -0.19 | 0 | — |
| 1.75 | 8 | -0.03 | 0 | — ← |
| 2 | 8 | -0.39 | 0 | — |
| 2.5 | 6 | -0.61 | 0 | — |
| 3 | 6 | -0.59 | 0 | — |

## Lecture

**Aucun multiple ne survit au test.** Le stop n'est pas le levier qui rend cette stratégie positive sur ces couples — l'information vaut mieux que six mois d'essais manuels.
