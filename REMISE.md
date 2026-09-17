# REMISE — tout le travail, en un seul endroit

> **Claude Code : c'est le point d'entrée. Lis-le en entier, puis va dans
> `APPLIQUER.md`.**
> Tout est à la racine de `/Users/arf/Trading Claude/`.
> `python3 verif.py` → **VERT · 320 tests** · 17/09/2026.

---

## En trente secondes

| Question | Réponse | Où |
|---|---|---|
| Par quoi je commence ? | **`APPLIQUER.md` étape 1** | 11 étapes, code compris |
| Qu'est-ce qui existe déjà ? | 16 modules, 320 tests | `ETAT.md` |
| Pourquoi cet ordre ? | les chiffres qui décident | `CHANTIER.md` |
| À quoi ça doit ressembler ? | `maquette.html` · `direction_vue.html` | s'ouvrent au navigateur |

**Ne réécris aucun module de la liste ci-dessous.** Ils sont testés. Ton
travail est de les BRANCHER dans `gold_agent/` et `web.py`.

---

## Les quatre chiffres qui commandent tout le reste

**1. Le hasard vaut 32 %, pas 50 %.**
À un R:R de 2,17, une pièce lancée touche le TP 31,5 % du temps. Le système
est à **21,7 %** — soit **9,8 points SOUS le hasard**. Pas un edge faible :
un edge **négatif**.

**2. La note est à l'envers.**

| note annoncée | n | taux RÉEL |
|---|---:|---:|
| 0 – 20 % | 37 | 22 % |
| 20 – 40 % | 224 | **25 %** |
| 40 – 60 % | 144 | **17 %** |

Plus le système est confiant, moins il a raison. **Ne filtre jamais sur la
note** — ça sélectionne les perdants. (J'avais proposé un seuil à 0,35 ; je
l'ai retiré, l'erreur est laissée barrée dans `APPLIQUER.md` §2.2.)

**3. 314 SL sur 317 sont `indeterminé`.**
Pas « les stops vont bien » : le module **ne peut pas répondre**, l'ATR
manque au journal. Tant que c'est vrai, personne ne peut dire si tu perds à
cause des stops ou de l'analyse. C'est l'étape 1, et c'est LE blocage.

**4. Avec un stop à 1,5 ATR, mesuré sur 3 ans : +1,12R.**
Ce chiffre est sur ta carte H4, affiché en rouge alors qu'il est positif.
C'est la meilleure nouvelle du projet : **ta stratégie devient rentable dès
que le stop est placé honnêtement.** C'est l'étape 2.

---

## Les 16 modules

| Fichier | Rôle | Tests |
|---|---|---:|
| `statistiques.py` | hasard · Wilson · Bonferroni · marge de bruit | — |
| `garde_fous.py` | stop minimum · anti-contradiction · suivi des SL | 25 |
| `superviseur_apprenant.py` | AG-00 — audit SL, calibration, poids, seuil | 30 |
| `parametres_agents.py` | réglage automatique, walk-forward corrigé | 16 |
| `chercheur_sous_ensembles.py` | où se cache un taux élevé | 17 |
| `avocats.py` | **AG-16 + AG-18** — le débat contradictoire | 25 |
| `figures.py` | **34 figures chartistes** + référence de bruit | 35 |
| `direction.py` | **AG-19 Directeur** — la direction sur toutes les sources | 33 |
| `cerveau.py` | **la boucle vivante** — apprend, journalise, s'affiche | 30 |
| `pips.py` | pips gagnés/perdus par instrument | 21 |
| `vue_instrument.py` | tout par instrument — taux, 5 TF, badges | 29 |
| `constellation_agent.py` | AG-09 Constellation + AG-10 Miroir | 20 |
| `agents_marches.py` | AG-11..15 marchés + intermarchés | 22 |
| `constellations.py` | explorateur de corrélations (CLI) | — |
| `graphe_agents.py` | réseau d'agents + positions pour/contre/neutre | 17 |
| `verif.py` | contrôle automatique du projet | — |

**Gabarits HTML** — autonomes, s'ouvrent au navigateur :
`maquette.html` (site, thème clair) · `direction_vue.html` (boussole) ·
`graphe.html` (réseau) · `cerveau_bandeau.html` (bandeau superviseur)

---

## Les figures : ce que j'ai fait de tes planches

**34 figures détectées**, mécaniquement, sans subjectivité.

| Prix (17) | Bougies (17) |
|---|---|
| triangle ascendant · descendant · symétrique | marteau · marteau inversé · pendu |
| biseau ascendant · descendant | étoile filante · doji · toupie |
| rectangle · canal haussier · baissier | englobante haussière · baissière |
| double sommet · creux | pénétrante · couverture en nuages |
| triple sommet · creux | étoile du matin · du soir |
| épaule-tête-épaule · inverse | trois soldats · trois corbeaux |
| drapeau haussier · baissier | |
| élargissement · tasse-anse | |
| arrondi sommet · creux | |

### 🔴 Le chiffre qu'il faut lire avant de s'en réjouir

J'ai lancé le détecteur sur **1 500 marches purement aléatoires** — aucune
tendance, aucune structure, du bruit :

```
avec 17 figures : 90,0 % des graphiques ALÉATOIRES en contiennent une · 1,68 par graphique
avec 34 figures : 98,3 % ·············································· · 2,94 par graphique
```

**Doubler le catalogue n'a pas doublé la lecture du marché : ça a doublé les
façons de trouver quelque chose dans du hasard.** Sur un graphique aléatoire,
on voit désormais presque toujours trois figures.

Un double sommet apparaît dans **28,9 %** du bruit. Une épaule-tête-épaule
dans **8,4 %**. Voir une figure n'est donc pas une information — c'est la
situation normale.

### Ce que dit la recherche

- **Bulkowski**, ~13 900 figures, 1991-2008 : taux d'échec **doublé**, 14 % →
  28 %, 44 % au pic — et seulement pour atteindre +10 %.
- **Roberts & al. (Cambridge)**, 8 ans de tick GBP/USD, hors échantillon :
  l'épaule-tête-épaule est **perdante sur les 5 échelles de temps**,
  −28 à −37 pips.
- **Lo, Mamaysky & Wang** (*Journal of Finance*, 2000) : information
  incrémentale, rentabilité après coûts **non établie**.
- **Bougies, S&P 500, 1950-2017** : aucun pouvoir prédictif sur les clôtures.

### Donc : poids par défaut ZÉRO

Une figure sort du module comme un **fait mesuré**, jamais comme un signal.
Elle ne pèse sur aucune décision tant que `calibrer()` n'a pas montré qu'elle
précède un gain **sur ton journal**, avec au moins 30 observations.

> Le seul résultat encourageant de toute cette littérature : chez Cambridge,
> **le filtre sur les ATTRIBUTS a amélioré 69 % des cas alors que la figure
> seule perdait.** Pas « épaule-tête-épaule », mais « épaule-tête-épaule AVEC
> telle proportion ». D'où le champ `mesures` : chaque figure porte ses
> attributs chiffrés pour que `chercheur_sous_ensembles.py` puisse les tester.

---

## Les agents

| Code | Nom | État |
|---|---|---|
| AG-00 | Superviseur apprenant | ✅ `superviseur_apprenant.py` |
| AG-01..05 | Vigie · Structure · Stratège · Traceur · Minières | ✅ ton projet |
| AG-09 · AG-10 | Constellation · Miroir | ✅ `constellation_agent.py` |
| AG-11..15 | Forex · Crypto · Matières · Actions · Intermarchés | ✅ `agents_marches.py` |
| AG-16 · AG-18 | **Avocat du diable · Avocat de la défense** | ✅ `avocats.py` |
| AG-19 | **Directeur** — direction du marché | ✅ `direction.py` |
| AG-99 | Vérificateur | ✅ `verif.py` |
| AG-06 · AG-07 | Probabilité · Opportunités | ⬜ **fondus dans AG-00** |
| AG-17 | Rattrapage | ⬜ jamais construit |

---

## Les règles qui ne se négocient pas

Elles priment sur tout le reste. Une consigne qui les contredit a tort.

1. **On n'optimise jamais le taux de réussite.** On pilote le R total.
2. **Un signal jamais entré ne compte dans aucun taux ni aucun pip.**
3. **Sous 20 résolus** : « échantillon insuffisant » **à la place** du
   pourcentage, jamais à côté.
4. **Stop minimum 1 ATR**, jamais assoupli.
5. **Un paramètre à la fois.**
6. **Le défaut d'une position est « neutre », jamais « pour ».**
7. **Ne jamais désactiver un contrôle de `verif.py`.**
8. **Tout changement automatique est journalisé et réversible.**
9. **Une mesure passe devant une opinion.** Conviction 83 % contre
   walk-forward −0,44R → c'est le −0,44R qui prend la place principale.
10. **Aucun chiffre n'est global.** Toujours rattaché à un instrument.
11. **Tout taux sort avec son effectif et son intervalle.**
12. **Toute performance se compare au hasard**, jamais à 50 %.
13. **Jamais plus de 2 conditions combinées** pour un sous-ensemble.
14. **Un agent dont la conclusion est connue d'avance ne vote pas.**
15. **Une recherche sur N valeurs exige une preuve corrigée de N.**
16. **Décrire n'est pas prédire.** Une source descriptive part à 1,0, une
    source prédictive à 0,0.

---

## Le fil rouge des quatre modules « cerveau »

Ils appliquent tous la même idée, et c'est volontaire :

```
avocats.py    un avocat qui plaide toujours ne plaide pas
figures.py    98 % du bruit contient une figure — en voir n'est pas une information
direction.py  « INDÉTERMINÉE » est une réponse ; sur 4 cas de démo, il s'abstient 3 fois
cerveau.py    on n'apprend que de données NOUVELLES ; un poids ne saute pas
```

**Un module dont la sortie est connue d'avance ne porte aucune
information — même quand cette sortie a l'air intelligente.**

C'est aussi ce que disent tes propres rapports : trois agents ont voté
pareil **403 fois sur 403**. Ils ne votaient pas, ils récitaient.

---

## L'ordre, et rien d'autre

```
🔴 étape 1   les 3 champs du journal        ← SANS ÇA, RIEN N'APPREND
🔴 étape 2   le stop minimum                ← +1,12R mesuré t'attend ici
🔴 étape 3   anti-contradiction
🔴 étape 4   le rapport du superviseur
🟠 étape 5   pips à la place du Profit Factor (+ le bug du 0.00)
🟠 étape 6   le débat AG-16/AG-18
🟠 étape 6bis AG-19 Directeur
🟠 étape 7   le graphe pour/contre/neutre
🟠 étape 8   le site : thème clair, par instrument, 5 TF
🟠 étape 10  le cerveau vivant sur tout le site
⚪ étape 9   vérification finale
```

**Si tu ne fais qu'une chose : l'étape 1.** Les 314 `indeterminé` bloquent
tout l'apprentissage en aval.

---

## À quoi s'attendre

Après les étapes 1 à 4, **le nombre de signaux va chuter très fortement** —
peut-être de 651 à quelques dizaines. **C'est le résultat recherché.** Un
système qui émet 651 signaux à 21,7 % ne souffre pas d'un manque de signaux.

Et la seule piste survivante des 26 sous-ensembles testés :

```
vente + marché crypto   n=97   35 %   IC [21 %–53 %]   +0,01R   hors : 42 %
```

Mieux hors échantillon que dedans — le meilleur signe possible. Mais la borne
basse est à **21 %** et l'espérance à **+0,01R**. C'est une piste, pas une
stratégie. Laisse-la atteindre 200 résolus avant d'en faire quoi que ce soit.

---

## La vérification

```bash
python3 verif.py                 # VERT
python3 -m pytest tests/ -q      # 320 passed
```

Puis les trois contrôles que seul un humain peut faire :

1. **Le nombre de signaux a-t-il chuté ?** Sinon l'étape 2 n'est pas branchée.
2. **Le verdict `INDÉTERMINÉE` apparaît-il dans le journal ?** Si tous les
   signaux ont une direction, quelque chose court-circuite AG-19.
3. **Reste-t-il des SL à `indeterminé` ?** Si oui, l'étape 1 est incomplète.
