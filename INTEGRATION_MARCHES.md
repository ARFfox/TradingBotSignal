# Brancher les 4 marchés et le graphe — note pour Claude Code

> À lire avec `SYSTEME.md`. Le module `agents_marches.py` est écrit et testé
> (22 tests). Il ne reste qu'à le brancher.

---

## 1. Ce qui est fourni

`agents_marches.py` expose :

```python
m = MatriceMarches(prix)          # prix : DataFrame, colonnes = tickers

m.agents["crypto"].etat()         # EtatMarche : largeur, cohésion, régime…
m.agents["crypto"].etat().carreaux  # list[Carreau] pour la grille
m.tuiles()                        # les 4 tuiles du niveau 1
m.correlations()                  # matrice 4×4 entre composites
m.avance_retard()                 # qui bouge en premier
m.graphe(seuil=0.20)              # {noeuds, liens} pour la vue graphe

m.agents["forex"].carte_agent("AG-11")   # carte au format du panneau
m.carte_agent("AG-15")
```

Codes d'agent : `AG-11` Forex · `AG-12` Crypto · `AG-13` Matières ·
`AG-14` Actions · `AG-15` Intermarchés.

**Une seule classe `AgentMarche`, instanciée quatre fois.** Ne surtout pas la
dupliquer en quatre classes : elles divergeraient, une correction serait
appliquée au crypto et oubliée sur le forex, et le système mentirait sur un
marché sans que personne ne le voie. Ce qui change d'un marché à l'autre est
dans le dictionnaire `MARCHES` — ce sont des **données**, pas du code.
Ajouter un actif ne demande aucune ligne de code.

---

## 2. Les données

Même contrainte que la constellation, et pour la même raison : **~40 actifs
sur 2 ans, jamais depuis le rendu de la page, jamais via Twelve Data**.

Réutilise `constellation_source.py` en élargissant son univers :

```python
TICKERS = sorted(set(constellation_agent.NOMS) |
                 {t for m in agents_marches.MARCHES.values() for t in m["tickers"]})
```

Une seule requête `yfinance`, un seul cache, deux consommateurs. Recalcul
toutes les 6 h, la page lit le cache.

---

## 3. Dans `collecter()`

Après le bloc constellation, même motif (try/except large, chrono) :

```python
t0 = time.perf_counter()
paquet["marches"] = None
try:
    from agents_marches import MatriceMarches, CODES
    px = constellation_source.prix()
    if px is not None:
        mm = MatriceMarches(px)
        paquet["marches"] = {
            "tuiles": mm.tuiles(),
            "grilles": {k: [vars(c) for c in a.etat().carreaux]
                        for k, a in mm.agents.items()},
            "etats": {k: {x: v for x, v in vars(a.etat()).items() if x != "carreaux"}
                      for k, a in mm.agents.items()},
            "correlations": mm.correlations().round(3).to_dict(),
            "avances": mm.avance_retard(),
            "graphe": mm.graphe(),
            "cartes": [mm.agents[k].carte_agent(CODES[k]) for k in mm.agents]
                      + [mm.carte_agent("AG-15")],
        }
except Exception as e:
    _evt("marches", f"indisponible : {e}", "warn")
paquet["chrono"]["marches"] = (time.perf_counter() - t0) * 1000
```

Dans `agents_live()`, il suffit ensuite de faire :

```python
agents.extend((d.get("marches") or {}).get("cartes", []))
```

Les cartes sont déjà au format exact du panneau — c'est testé
(`test_cartes_au_format_du_panneau`).

---

## 4. Les trois niveaux d'interface

### Niveau 1 — les 4 tuiles

Depuis `tuiles()`. Chaque tuile porte :

```
🪙 CRYPTO                    +11,2 %
haussier large, en bloc
10 actifs · largeur 100 %
cohésion +0,74 · leader BNB
```

⚠️ **`variation_pct` et `largeur` ne mesurent pas la même chose et peuvent
diverger.** `variation_pct` est la performance du composite sur 20 jours ;
`largeur` est la part de membres dont la tendance moyen terme est haussière.
Un marché peut être haussier de tendance et négatif sur les 20 derniers jours
— c'est une information, pas une incohérence. L'interface doit afficher les
deux séparément et ne jamais les fusionner en un seul chiffre.

### Niveau 2 — la grille

Clic sur une tuile → `grilles[marche]`, déjà trié par performance
décroissante. Chaque carreau porte `ticker`, `variation_pct`, `biais`,
`force_relative`, `role`.

**`force_relative` est le champ intéressant** : c'est la performance moins la
médiane du marché. Il répond à « cet actif fait-il mieux que son marché ? »,
ce que la performance brute ne dit pas. Dans un crypto qui monte de 11 %, un
actif à +8 % est un **retardataire**, pas un gagnant.

Dégradé de couleur sur `force_relative`, pas sur `variation_pct` : sinon dans
un marché haussier tous les carreaux sont verts et la grille ne dit rien.

### Niveau 3 — le graphe

`graphe()` retourne directement `{noeuds, liens}` :

- **nœud** : `id`, `nom`, `emoji`, `coul`, `taille` (nb d'actifs), `regime`,
  `variation_pct`, `largeur`
- **lien** : `de`, `vers`, `corr`, `sens`, `epaisseur`, `meneur`, `jours`

Rendu : force-directed, épaisseur du trait = `epaisseur`, trait plein pour
une corrélation positive, pointillé pour une négative, **flèche uniquement
quand `jours > 0`** (un marché qui en devance un autre).

Le seuil par défaut (0,20) est là pour une raison : **un graphe où tout est
relié à tout ne montre rien.** Sur les données de test, 4 marchés donnent 1
seul lien — c'est le bon comportement, pas un bug.

Tu peux réutiliser le moteur 3D déjà en place pour les agents, ou faire une
vue 2D séparée. Le format de données est le même.

---

## 5. Le piège de l'avance/retard

`avance_retard()` teste 11 décalages (−5 à +5 jours) par paire. **Au seuil
statistique habituel, un maximum apparaît par pur hasard dans environ 43 %
des cas.** Sur le jeu de test où une seule avance était injectée, la première
version en annonçait deux — dont une entièrement fabriquée.

D'où `Z_SIGNIFICATIF = 2.8` (correction du test multiple) : une avance n'est
annoncée que si sa corrélation dépasse `2,8/√n` **et** bat le décalage zéro
d'une marge nette. Le test `test_aucune_avance_inventee_ailleurs` verrouille
ce comportement.

**Ne pas baisser ce seuil pour « voir plus de relations ».** Sur des marchés
liquides et des données quotidiennes, l'avance réelle est le plus souvent
nulle, et « simultané » est la bonne réponse. Une avance affichée à tort
pousse à entrer sur un marché en croyant lire l'avenir d'un autre.

---

## 6. Ordre de travail

| # | Étape | Vérification |
|---|---|---|
| 1 | élargir l'univers de `constellation_source.py` | une seule requête, cache partagé |
| 2 | bloc `marches` dans `collecter()` | `paquet["marches"]` rempli, page < 2 s |
| 3 | `agents.extend(...)` — les 5 cartes | AG-11 à AG-15 dans le panneau |
| 4 | les 4 tuiles | régime et largeur affichés |
| 5 | la grille par marché | dégradé sur `force_relative` |
| 6 | le graphe | ≤ 6 liens, flèches seulement si `jours > 0` |

`python3 verif.py` après chaque étape. Les 42 tests doivent rester verts.

---

## 7. Ce qu'il ne faut pas faire

- ❌ Dupliquer `AgentMarche` en quatre classes
- ❌ Écrire un régime en dur — il se déduit de `largeur` + `cohesion`
- ❌ Colorer la grille sur `variation_pct` (tout serait vert en marché haussier)
- ❌ Baisser `Z_SIGNIFICATIF` pour afficher plus d'avances
- ❌ Afficher une flèche d'avance quand `jours == 0`
- ❌ Fusionner `variation_pct` et `largeur` en un seul indicateur
