# Superviseur autonome — spécification pour Claude Code

> À exécuter avec `SYSTEME.md`. Module fourni et testé : `superviseur_apprenant.py`
> (30 tests, `python3 -m pytest tests/ -q` → 71 verts au total).

---

## 0. Ce que disent les chiffres, avant de coder quoi que ce soit

```
548 émis · 288 résolus · 68 TP / 220 SL · 23,6 % · −77,98R · PF 0,00
```

Décomposé :

| | |
|---|---|
| Gain moyen par TP | **+2,09R** |
| Espérance par signal | **−0,271R** |
| Taux nécessaire à l'équilibre | **32,4 %** |
| Écart à combler | **8,8 points**, pas 56 |
| Perte en capital à 0,5 %/trade | **−39 %** |

**Le R:R n'est pas le problème.** À 2,09R de gain moyen, il suffit de 32,4 %
de réussite pour être à l'équilibre. Il en manque 8,8 points — pas 56.

Et c'est pour ça que **viser 80 % est le mauvais objectif**. Le moyen le plus
simple d'atteindre 80 % est de rapprocher le TP de l'entrée : on gagne
souvent, très peu, et une seule perte efface dix gains. On peut afficher 95 %
de réussite avec un système qui ruine un compte.

Ce qui se pilote est l'**espérance**. Le taux de réussite est un sous-produit
qu'on affiche, jamais une cible qu'on poursuit. Le module optimise le R total.

---

## 1. Trois pannes visibles dans tes propres captures

### Panne 1 — les stops sont sous le bruit

```
CUIVRE  M5   entrée 6.50   SL 6.49   TP 6.53
```

Un stop à **0,01 sur le cuivre**, c'est 2 à 5 fois le spread. Sur du M5, ce
n'est pas une invalidation, c'est du bruit : le prix le touche en respirant.
Idem `DOGE/USD` entrée 0.08 / SL 0.08 / TP 0.08 — les trois valeurs sont
identiques à l'affichage.

C'est probablement la **première cause des 220 SL**.

### Panne 2 — le système émet des signaux contradictoires

```
12:17  GDX  M15  VENTE  94.32
12:17  GDX  M5   ACHAT  93.86
```

Le même instrument, la même minute, deux sens opposés. Quoi qu'il arrive,
l'un des deux perd. Ça n'est pas un désaccord entre timeframes à arbitrer :
c'est un signal qui n'aurait jamais dû sortir.

### Panne 3 — la porte d'émission est ouverte

La colonne NOTE affiche **23 % à 47 %**. Le système émet des signaux à
23 % de confiance. 548 signaux dont beaucoup dans la même minute.

**Un système qui émet tout n'a pas de superviseur.** Il a un afficheur.

---

## 2. Le module `superviseur_apprenant.py`

```python
from superviseur_apprenant import (
    Signal, rapport, bilan,
    auditer_sl, rapport_stops,          # pourquoi les stops sautent
    courbe_calibration, ecart_calibration,
    poids_agents,                       # poids MESURÉS
    esperance_par_combo,                # qui a le droit d'émettre
    seuil_optimal,                      # par le R total
    filtrer_emission,                   # doublons + contradictions
)
```

### 2.1 L'audit des stops — la brique qui manque le plus

Derrière un même « SL » se cachent **deux pannes opposées** :

| Cause | Diagnostic | Correction |
|---|---|---|
| **Stop trop serré** | le TP a été atteint **après** le stop, ou le stop était sous 1 ATR | élargir le stop — **ne pas toucher à l'analyse** |
| **Direction fausse** | le prix n'a jamais progressé de plus de 0,25R | revoir les conditions d'entrée — **ne pas toucher au stop** |

Les confondre, c'est corriger l'analyse quand le problème est le stop, et
inversement. **C'est comme ça qu'un système tourne en rond pendant des mois.**

Pour que ça fonctionne, `journal.py` doit enregistrer deux champs de plus :

```python
"atr": float,                  # ATR du timeframe AU MOMENT de l'émission
"extreme_favorable": float,    # meilleur prix atteint avant la résolution
"tp_atteint_apres_sl": bool,   # suivi du prix pendant l'horizon du trade
```

Sans `atr`, aucun stop ne peut être jugé. Sans `tp_atteint_apres_sl`, la
distinction entre les deux pannes est impossible. **Ces trois champs sont la
priorité absolue** — tout le reste du module en dépend.

### 2.2 La note est-elle calibrée ?

`courbe_calibration()` répond à : *un signal noté 40 % gagne-t-il 40 % du
temps ?* Si les signaux notés 45 % gagnent 25 %, la note ment — et tout ce
qui s'appuie dessus (seuil, priorité, taille) est faux.

C'est le **premier contrôle**, avant toute autre optimisation. Au-delà de
15 % d'écart moyen, la note n'est pas utilisable comme probabilité.

### 2.3 Les poids des agents — et le « boost » que tu demandes

Tu veux que les agents montent à 200 % ou plus. Deux choses différentes se
cachent là-dedans :

- **Une conviction ne peut pas dépasser 100 %.** C'est une probabilité. Un
  agent « sûr à 200 % » n'existe pas — afficher 200 % ne rend pas l'agent
  meilleur, ça rend l'échelle fausse et plus rien n'est comparable.
- **Un poids, lui, est relatif et peut largement dépasser 1.** Le module
  autorise **jusqu'à ×3** : un agent peut peser trois fois plus qu'un autre
  dans le vote. **C'est ça, booster un agent** — et ça, c'est mesuré.

Le poids vient du **pouvoir discriminant** : l'écart de R entre les signaux
où l'agent était d'accord et ceux où il ne l'était pas.

```
AG-03   n=187   poids ×1.21   discr. +0.21   utile
AG-02   n=213   poids ×0.88   discr. -0.12   sans pouvoir discriminant
AG-Y    n=200   poids ×0.10                  vote toujours pareil — sans valeur
AG-Z    n=180   poids ×0.10   discr. -0.31   contre-indicateur — inverser son vote
```

Deux cas que le module détecte et qu'aucun réglage manuel n'aurait trouvés :

- **L'agent qui vote toujours pareil** est écarté même s'il a un bon taux
  apparent. Un agent qui dit « haussier » sur tout a raison la moitié du
  temps et n'apporte **aucune** information.
- **Le contre-indicateur** : un agent systématiquement du mauvais côté est
  une information précieuse — il suffit d'inverser son vote.

### 2.4 Le seuil d'émission

`seuil_optimal()` balaye les seuils et retient celui qui maximise le **R
total**. Et il peut répondre :

```
AUCUN seuil ne rend le système positif — le problème n'est pas le
filtrage, c'est la stratégie elle-même
```

**C'est l'issue la plus probable sur tes données actuelles, et c'est la
réponse la plus utile que le module puisse donner.** Un seuil inventé qui
affiche un joli chiffre ne ferait que perdre moins vite.

### 2.5 Les garde-fous

`filtrer_emission()` applique, dans l'ordre :

1. note < seuil → refusé
2. couple (instrument × tf) à espérance mesurée négative → refusé
3. stop sous 1 ATR → refusé
4. **contradiction** : même instrument, sens opposé déjà retenu → refusé
5. **doublon** : même instrument, même sens, moins de 30 min → refusé

Le meilleur candidat est traité en premier, donc en cas de contradiction
c'est le plus fort qui survit. Chaque refus est journalisé avec son motif —
tu dois pouvoir savoir **pourquoi** un signal n'est pas sorti.

---

## 3. L'onglet Signaux validés — la règle que tu demandes

> **Un signal ne compte que s'il a touché son point d'entrée.**
> Touche le TP → **validé**. Touche le SL → **non validé**.
> Jamais entré → **il ne compte pas du tout**, ni au numérateur ni au dénominateur.

```python
resolus  = [s for s in emis if s.statut in ("TP", "SL")]
valides  = [s for s in resolus if s.statut == "TP"]
taux     = len(valides) / len(resolus)
```

Affichage, dans cet ordre :

```
  −77.98R          23.6 %              288 / 548            0.00
  R cumulé      signaux validés      résolus / émis    profit factor
  ce qui compte   68 TP / 220 SL

  Équilibre à 32,4 % avec un gain moyen de +2,09R — il manque 8,8 points.
```

Cette dernière ligne est le cœur de l'onglet : elle transforme « 23,6 % » en
objectif atteignable. Sans elle, le pourcentage ne dit pas quoi corriger.

---

## 4. La boucle d'apprentissage

Le superviseur tourne **toutes les 24 h**, ou dès que 20 nouveaux signaux
sont résolus :

```
1. résoudre les signaux échus (TP / SL / expiré)
2. auditer chaque SL → stop trop serré ou direction fausse
3. recalculer la courbe de calibration de la note
4. recalculer les poids des agents (bornés 0,1× à 3×)
5. recalculer l'espérance par couple → AUTORISE / COUPE / OBSERVATION
6. recalculer le seuil d'émission qui maximise le R total
7. écrire rapport_superviseur.md
```

### Trois garde-fous obligatoires sur l'auto-apprentissage

**Un système qui se modifie seul peut aussi se dégrader seul.**

1. **Aucune décision sous l'effectif minimum.** 20 résolus pour juger un
   couple, 30 pour pondérer un agent, 50 pour fixer un seuil. En dessous,
   le module garde la valeur neutre. Un poids calculé sur 5 signaux est du
   bruit promu au rang de règle.
2. **Les bornes ne bougent pas.** Poids entre 0,1× et 3×, stop ≥ 1 ATR,
   risque ≤ 0,5 %. Le superviseur ajuste **à l'intérieur** de ces bornes,
   il ne les déplace jamais. Sans ça, une série chanceuse le pousse à
   tout miser sur un agent.
3. **Chaque changement est journalisé et réversible.** `historique_calibration.json`
   garde l'ancienne valeur, la nouvelle, et sur quel effectif. Si les
   résultats se dégradent après une recalibration, on doit pouvoir revenir
   en arrière et savoir quoi accuser.

---

## 5. Le graphe des requêtes

Tu veux voir **qui envoie des requêtes au superviseur et qui n'en envoie pas**.
`graphe_agents.py` a déjà les nœuds et les liens ; il manque le trafic. Trois
champs à ajouter sur chaque lien vers AG-00 :

```python
{"de": "AG-02", "vers": "AG-00",
 "requetes_24h": 1284,      # combien d'avis envoyés
 "utilisees": 412,          # combien ont pesé dans une décision
 "poids": 0.88}             # son poids mesuré actuel
```

Rendu :

- **épaisseur du trait** = `requetes_24h` (le volume)
- **opacité** = `utilisees / requetes_24h` (l'utilité)
- **un agent à 0 requête** = trait en pointillés gris + case « MUET »
- **un agent qui envoie beaucoup et dont rien n'est utilisé** = trait épais
  et transparent. C'est le motif visuel le plus important du graphe : il
  désigne un agent qui coûte du calcul et n'apporte rien.

Le nombre affiché sur la case reste la **conviction en 0–100 %**. Le poids
s'affiche à côté sous la forme `×2.1` — c'est là que se voit le « boost ».

---

## 6. Ordre de travail

| # | Étape | Pourquoi cet ordre | Vérification |
|---|---|---|---|
| 1 | **3 champs dans `journal.py`** : `atr`, `extreme_favorable`, `tp_atteint_apres_sl` | rien ne fonctionne sans eux | nouveaux signaux complets |
| 2 | **Stop minimum 1 ATR + spread** | 🔴 corrige la panne n°1 | plus aucun stop sous 1 ATR |
| 3 | **Anti-contradiction / anti-doublon** | 🔴 corrige la panne n°2 | plus de GDX achat+vente |
| 4 | Brancher `rapport()` → `rapport_superviseur.md` | le diagnostic devient visible | le rapport s'écrit |
| 5 | Onglet Signaux validés + ligne d'équilibre | mesure honnête | expirés exclus |
| 6 | Poids des agents dans le vote | l'apprentissage commence | les poids bougent seuls |
| 7 | Seuil d'émission depuis `seuil_optimal()` | 🔴 corrige la panne n°3 | l'émission chute fortement |
| 8 | Trafic sur le graphe | on voit qui travaille | requêtes affichées |

**Les étapes 1 à 3 valent plus que toutes les autres réunies.** Elles ne
demandent aucune intelligence : juste un stop qui n'est pas dans le bruit et
un système qui ne se contredit pas.

---

## 7. Ce qu'il ne faut pas faire

- ❌ Optimiser le taux de réussite. Optimiser le R total.
- ❌ Viser 80 %. Un taux ne se décide pas, il se constate.
- ❌ Rapprocher le TP pour faire monter le pourcentage — c'est exactement
  ce qui détruit un compte en affichant de beaux chiffres
- ❌ Afficher une conviction supérieure à 100 %
- ❌ Calculer un poids sur moins de 30 signaux résolus
- ❌ Laisser le superviseur modifier ses propres bornes
- ❌ Compter les signaux jamais entrés dans le taux
- ❌ Émettre deux signaux opposés sur le même instrument

---

## 8. Ce à quoi il faut s'attendre

Après les étapes 1 à 3 et 7, **le nombre de signaux va chuter très fortement** —
peut-être de 548 à quelques dizaines. C'est le résultat recherché, pas une
régression. Un système qui émet 548 signaux à 23 % ne souffre pas d'un manque
de signaux.

Et il est possible que le module annonce qu'aucun seuil ne rend le système
positif. Ce serait un résultat utile : il dirait que le travail n'est pas
dans le filtrage mais dans les conditions d'entrée elles-mêmes — et il te
l'aurait dit sur **288 trades mesurés** plutôt qu'après six mois de doute.

C'est pour ça que ces 548 signaux, même perdants, sont la chose la plus
précieuse que le projet ait produite jusqu'ici. **C'est la première fois que
le système a de quoi apprendre.**
