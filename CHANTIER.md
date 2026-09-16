# CHANTIER — l'ordre de travail unique

> **Claude Code : lis ce fichier en premier, puis `SYSTEME.md`.**
> Tous les autres documents sont des références. Celui-ci dit quoi faire,
> dans quel ordre, et comment savoir que c'est fini.
> État au 16/09/2026 — 129 tests verts.

---

## Le chiffre qui décide de tout

```
548 émis · 288 résolus · 68 TP / 220 SL · 23,6 % · −77,98R · PF 0,00
```

Gain moyen **+2,09R** → l'équilibre est à **32,4 %**. Il manque **8,8 points**,
pas 56. Le R:R n'est pas le problème.

**On n'optimise jamais le taux de réussite.** Le moyen le plus simple
d'atteindre 80 % est de rapprocher le TP de l'entrée : on gagne souvent, très
peu, et une perte efface dix gains. On pilote l'**espérance**. Le taux est un
résultat qu'on affiche.

### La référence que personne ne cite jamais

Avec TP à 2,09R et SL à 1R, une **marche au hasard** — aucune analyse, aucun
agent, une pièce lancée — touche le TP dans **32,4 %** des cas :

```
P(toucher +rr avant −1) = 1 / (1 + rr)
```

C'est exactement le seuil d'équilibre. Deux conséquences qu'il faut regarder
en face :

1. **23,6 % est 8,8 points SOUS le hasard.** Le système actuel n'a pas un
   edge faible : il a un edge **négatif**. Prendre l'inverse de chaque signal
   ferait mieux. La cause la plus probable n'est pas l'analyse mais la
   **géométrie** : un stop à 0,29 ATR n'a pas un R:R de 2,09, il a le R:R que
   le bruit lui laisse — c'est-à-dire beaucoup moins.
2. **80 % à R:R constant est un objectif énorme.** Il demande une dérive
   dirigée ~790 × supérieure au cas sans edge, et donnerait +1,47R par trade.
   Aucun fonds ne tient ça. Ce qui est atteignable : **45–55 % sur un
   sous-ensemble étroit**, ce qui donne déjà +0,4 à +0,6R par trade.

> Et 80 % mesuré sur 20 trades, c'est un intervalle de confiance
> **[59 % – 93 %]** : ça ne prouve rien. Il faut ~200 trades pour dire
> « 80 % » avec [74 % – 85 %]. Le module `chercheur_sous_ensembles.py`
> affiche systématiquement cet intervalle à côté du taux.

---

## Ce qui est déjà écrit et testé — ne pas réécrire

| Fichier | Rôle | Tests |
|---|---|---|
| `verif.py` | contrôle automatique du projet | — |
| `garde_fous.py` | stop minimum · anti-contradiction · **suivi des SL** | 25 |
| `superviseur_apprenant.py` | audit SL · calibration · poids · seuil | 30 |
| `parametres_agents.py` | réglage automatique avec walk-forward | 17 |
| `constellation_agent.py` | AG-09 Constellation + AG-10 Miroir | 20 |
| `agents_marches.py` | AG-11..15 marchés + intermarchés | 22 |
| `chercheur_sous_ensembles.py` | **où se cache le taux élevé** — Wilson + hors échantillon | 17 |
| `graphe_agents.py` · `graphe.html` | réseau d'agents | — |

**129 tests. `python3 verif.py` doit rester vert après chaque étape.**

---

## Les 4 étapes bloquantes — rien d'autre ne compte avant

### Étape 1 — Les 3 champs du journal 🔴

**Sans eux, tout le reste est affamé.** Le superviseur ne peut rien apprendre
d'un « SL » qui ne dit pas pourquoi.

Dans `gold_agent/journal.py`, ajouter à chaque signal :

```python
"emis": bool,                  # ce signal a-t-il été AFFICHÉ/NOTIFIÉ ?
"atr": float,                  # ATR du timeframe À L'ÉMISSION
"spread": float,               # spread constaté à l'émission
"extreme_favorable": float,    # rempli par garde_fous.suivre()
"tp_atteint_apres_sl": bool,   # rempli par garde_fous.suivre()
"r_realise": float | None,
"intermarche": dict,           # score, base, fiable (AG-10)
```

Puis remplacer la résolution actuelle par :

```python
from garde_fous import suivre
r = suivre(signal, bougies_depuis_emission)
signal.update({"statut": r.statut, "r_realise": r.r_realise,
               "extreme_favorable": r.extreme_favorable,
               "tp_atteint_apres_sl": r.tp_atteint_apres_sl})
```

**Fini quand :** un nouveau signal résolu porte les 7 champs, et
`superviseur_apprenant.auditer_sl()` renvoie autre chose qu'`indetermine`.

---

### Étape 2 — Le stop minimum 🔴

C'est la première cause des 220 SL. Cas réel : cuivre M5, entrée 6.50 /
SL 6.49 — **0,29 ATR**, soit 2 à 5 fois le spread. Le prix le touche en
respirant.

À l'émission, dans `gold_agent/strategy.py` :

```python
from garde_fous import valider_signal
v = valider_signal(entree, sl, tp, sens, atr, spread)
if not v["ok"]:
    return None          # refusé, avec v["motif"] journalisé
sl = v["sl"]             # stop élargi si nécessaire
```

⚠️ **L'ordre compte** : on élargit le stop D'ABORD, on vérifie le R:R
ENSUITE. Sur le cas cuivre, le R:R tombe à **0,86** après élargissement —
le setup ne tenait que par un stop irréaliste. Il doit être refusé.

**Fini quand :** aucun signal émis n'a un stop sous 1 ATR, et le nombre de
signaux émis chute nettement. **La chute est le résultat recherché.**

---

### Étape 3 — Anti-contradiction 🔴

Cas réel : `12:17 GDX M15 VENTE` et `12:17 GDX M5 ACHAT`. Quoi qu'il arrive,
l'un des deux perd.

```python
from garde_fous import filtrer_lot
gardes, refuses = filtrer_lot(candidats)
for r in refuses:
    _evt("emission", f"refusé {r['instrument']} {r['tf']} : {r['motif']}")
```

**Fini quand :** plus aucun couple achat/vente sur le même instrument, et
chaque refus est visible avec son motif. Tu dois pouvoir savoir **pourquoi**
un signal n'est pas sorti.

---

### Étape 4 — Le rapport du superviseur 🔴

```python
from superviseur_apprenant import rapport, charger_journal
Path("rapport_superviseur.md").write_text(rapport(charger_journal(JOURNAL)))
```

À lancer toutes les 24 h, ou dès 20 nouveaux résolus.

**Fini quand :** le rapport affiche la répartition des causes de SL, la
courbe de calibration, les poids mesurés des agents, et un verdict sur le
seuil d'émission.

> ⚠️ **Il annoncera peut-être qu'aucun seuil ne rend le système positif.**
> C'est l'issue probable et c'est la réponse la plus utile : elle dirait que
> le travail est dans les conditions d'entrée, pas dans le filtrage — sur
> 288 trades mesurés au lieu de six mois de doute.

---

### Étape 5 — Où se cache le taux élevé 🔴

C'est la réponse à « je veux 80 % sans toucher aux pips ». On ne **décide**
pas d'un taux : on **cherche** où il existe déjà, dans les 548 signaux.

```python
from chercheur_sous_ensembles import rapport
from superviseur_apprenant import charger_journal
Path("rapport_sous_ensembles.md").write_text(rapport(charger_journal(JOURNAL)))
```

Le module découpe le journal en sous-ensembles (« achat **et** stop ≥ 1,5 ATR »,
« note ≥ 40 % **et** session Londres », …), et pour chacun il donne :

| Ce qu'il affiche | Pourquoi c'est là |
|---|---|
| taux de réussite | le chiffre demandé |
| **intervalle de Wilson** | 4/5 et 160/200 ne sont pas la même affirmation |
| taux du hasard à ce R:R | la seule référence honnête |
| R moyen | le taux ne paie pas les factures, le R oui |
| **taux hors échantillon** | le motif tient-il sur des signaux jamais vus |

Verdicts possibles : `HASARD` · `NON VÉRIFIÉ` · `NON CONFIRMÉ` (beau sur le
passé, effondré sur la suite) · `PROMETTEUR` · `EDGE SOLIDE` · `ATTEINT 80 %`.

Deux règles de méthode sont câblées dans le module et ne se négocient pas :

- **Maximum 2 conditions combinées.** Au-delà on ne sélectionne plus, on
  mémorise le passé.
- **Bonferroni sur la recherche, pas sur la vérification.** Tester 43
  hypothèses sur le passé exige une correction (sinon on trouve toujours
  quelque chose). Le hors-échantillon arrive déjà choisi : c'est **un** test,
  pas 43. Lui appliquer la même correction reviendrait à jeter une preuve
  indépendante.

**Fini quand :** le rapport nomme au moins un sous-ensemble `PROMETTEUR`
— ou dit clairement qu'il n'y en a aucun.

> Si aucun sous-ensemble ne dépasse le hasard, la conclusion n'est pas
> « il faut chercher plus fort » : c'est que le signal n'est pas dans le
> filtrage mais dans les **conditions d'entrée** (étapes 2 et 3). Dans ce cas
> le filtre le plus rentable reste le stop minimum.

---

## Ensuite seulement — par valeur décroissante

| # | Quoi | Référence | Pourquoi à ce rang |
|---|---|---|---|
| 6 | Onglet **Signaux validés** | `SPEC_SITE_V3.md` §7 | rend la mesure lisible ; expirés exclus, effectif affiché |
| 7 | **Poids des agents** dans le vote | `SPEC_SUPERVISEUR_AUTONOME.md` §2.3 | l'apprentissage commence vraiment |
| 8 | **Seuil d'émission** mesuré | idem §2.4 | remplace le seuil deviné |
| 9 | **Grille de conviction** (couple instrument × TF) | étape 5 | n'émettre que là où l'edge est mesuré positif |
| 10 | **CCXT** dans `feeds/` | `SKILL_OUTILS_EXTERNES.md` §1 | supprime ~300 lignes fragiles |
| 11 | **VectorBT** pour le balayage | idem §2 | rend possible le walk-forward complet |
| 12 | Registre d'instruments + navigation | `SPEC_SITE_V3.md` §1-5 | l'interface multi-marchés |
| 13 | Cases d'agents + graphe | `SPEC_SITE_V3.md` §6 · `INTEGRATION_GRAPHE.md` | lisibilité |
| 14 | **AG-18 Avocat de la défense** | `SKILL_OUTILS_EXTERNES.md` §3 | équilibre le débat face à AG-16 |
| 15 | `parametres_agents.py` branché | — | réglage automatique niveau 2 |
| 16 | Nouvelles stratégies (CRT, IFVG, ORB) | `SKILL_STRATEGIES.md` | **en dernier**, et chacune passe le backtest |

---

## Les règles qui ne se négocient pas

1. **Le taux de réussite ne se décide pas.** On optimise le R total.
2. **Un signal jamais entré ne compte dans aucun taux.**
3. **Sous 20 signaux résolus, afficher « échantillon insuffisant »** à la
   place du pourcentage, pas à côté.
4. **Stop minimum 1 ATR**, jamais assoupli.
5. **Le superviseur ajuste à l'intérieur des bornes, jamais les bornes.**
6. **Un paramètre à la fois**, jamais deux ensemble.
7. **Chercher sur le passé, juger sur un futur jamais vu.**
8. **Tout changement automatique est journalisé et réversible.**
9. **Aucune conviction au-dessus de 100 %.** Un poids peut aller à ×3.
10. **Ne jamais désactiver un contrôle de `verif.py`** — le signaler et
    proposer une règle plus précise.
11. **Tout taux affiché sort avec son effectif et son intervalle.** « 80 % »
    seul est une phrase vide.
12. **Toute affirmation de performance se compare au hasard**, jamais à 50 %.
    À 2,09R le hasard vaut 32,4 %.
13. **Jamais plus de 2 conditions combinées** pour définir un sous-ensemble.

---

## À quoi s'attendre

Après les étapes 1 à 4, **le nombre de signaux va chuter très fortement** —
peut-être de 548 à quelques dizaines. C'est le résultat recherché. Un système
qui émet 548 signaux à 23 % ne souffre pas d'un manque de signaux.

Et il est possible que le diagnostic conclue que la stratégie elle-même n'a
pas d'edge. Ce serait une mauvaise nouvelle utile : mieux vaut l'apprendre
sur 288 trades mesurés que sur six mois de plus.

**Ces 548 signaux perdants sont la chose la plus précieuse que le projet ait
produite. C'est la première fois que le système a de quoi apprendre.**
