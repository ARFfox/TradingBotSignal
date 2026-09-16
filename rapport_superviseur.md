# Rapport du Superviseur apprenant

généré le 2026-09-16 16:39 UTC · 553 signaux au journal · 355 résolus

```
==========================================================================
  SUPERVISEUR — AUTO-DIAGNOSTIC
==========================================================================

  -95.1R sur 355 résolus (553 émis, 198 jamais entrés)
  taux 23.7% · gain moyen +2.09R · équilibre à 32.3%
  ⚠ espérance -0.268R — il manque 8.6% points de réussite pour l'équilibre

  STOPS
    271 stops touchés · 1% par stop trop serré
    stop médian : 1.00 ATR · 100% sous 1.0 ATR
      indetermine          267
      stop_trop_serre      2
      direction_fausse     2

  CALIBRATION DE LA NOTE
    0%–20%     n=34   annoncé 11% → réel 21% · -0.42R
    20%–40%    n=192  annoncé 31% → réel 28% · -0.16R
    40%–60%    n=129  annoncé 44% → réel 19% · -0.39R
    écart moyen 12.0% — exploitable

  AGENTS (poids mesuré, pas choisi)
    AG-01  n=354  poids ×0.10   discr. +0.38   vote quasiment toujours pareil — sans valeur
    AG-10  n=354  poids ×0.10   discr. -0.38   vote quasiment toujours pareil — sans valeur
    AG-05  n=354  poids ×0.10   discr. -0.42   vote quasiment toujours pareil — sans valeur

  COUPLES INSTRUMENT × TIMEFRAME
    XAU/USD    M5    n=20   -0.562R  COUPE

  SEUIL D'ÉMISSION
    AUCUN seuil ne rend le système positif — le problème n'est pas le filtrage, c'est la stratégie elle-même

    Aucun filtrage ne sauve ce système. Filtrer plus fort ne
    fait que perdre moins vite. Il faut corriger les stops et
    les conditions d'entrée avant de rechercher un seuil.

```
