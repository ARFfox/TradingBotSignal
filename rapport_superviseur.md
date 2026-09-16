# Rapport du Superviseur apprenant

généré le 2026-09-16 18:16 UTC · 576 signaux au journal · 400 résolus

```
==========================================================================
  SUPERVISEUR — AUTO-DIAGNOSTIC
==========================================================================

  -66.8R sur 400 résolus (576 émis, 176 jamais entrés)
  taux 27.0% · gain moyen +2.08R · équilibre à 32.4%
  ⚠ espérance -0.167R — il manque 5.4% points de réussite pour l'équilibre

  STOPS
    292 stops touchés · 2% par stop trop serré
    stop médian : 1.00 ATR · 50% sous 1.0 ATR
      indetermine          283
      stop_trop_serre      6
      direction_fausse     3

  CALIBRATION DE LA NOTE
    0%–20%     n=37   annoncé 10% → réel 22% · -0.37R
    20%–40%    n=220  annoncé 31% → réel 31% · -0.04R
    40%–60%    n=143  annoncé 44% → réel 22% · -0.31R
    écart moyen 9.5% — exploitable

  AGENTS (poids mesuré, pas choisi)
    AG-01  n=395  poids ×0.10   discr. +0.48   vote quasiment toujours pareil — sans valeur
    AG-05  n=395  poids ×0.10   discr. -0.43   vote quasiment toujours pareil — sans valeur
    AG-10  n=395  poids ×0.10   discr. -0.48   vote quasiment toujours pareil — sans valeur

  COUPLES INSTRUMENT × TIMEFRAME
    XAU/USD    M5    n=20   -0.562R  COUPE

  SEUIL D'ÉMISSION
    AUCUN seuil ne rend le système positif — le problème n'est pas le filtrage, c'est la stratégie elle-même

    Aucun filtrage ne sauve ce système. Filtrer plus fort ne
    fait que perdre moins vite. Il faut corriger les stops et
    les conditions d'entrée avant de rechercher un seuil.

```
