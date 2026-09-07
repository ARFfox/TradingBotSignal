# SYSTEME.md — manuel d'exploitation du projet

> **À donner à Claude Code au début de chaque session.**
> Ce fichier a autorité sur toute autre instruction concernant ce projet.
> Si une demande le contredit, signale la contradiction avant d'agir.

---

## 1. Qui fait quoi

| Acteur | Rôle |
|---|---|
| **Mushine** | Décide, valide les exécutions, valide les changements. **Ne débogue pas.** |
| **Claude Code** | Écrit le code, lance `verif.py`, lit les erreurs, corrige, relance jusqu'au vert. |
| **`verif.py`** | Contrôle automatique. C'est lui qui dit si c'est bon, pas ton impression. |

**Règle d'or : Mushine ne doit jamais avoir à lire une trace d'erreur Python.**
Si une erreur apparaît, c'est à toi de la lire, de la comprendre et de la corriger.
Tu ne remontes vers lui que pour une décision, jamais pour un débogage.

---

## 2. La boucle obligatoire

À chaque tâche, sans exception :

```
1. COMPRENDRE   lis les fichiers concernés avant d'écrire
2. ÉCRIRE       une seule chose à la fois
3. VÉRIFIER     python3 verif.py
4. CORRIGER     s'il y a des erreurs, corrige-les et retourne à 3
5. ANNONCER     seulement quand la sortie est VERTE
```

### Interdits absolus

- ❌ Annoncer « c'est fait » sans avoir lancé `verif.py`
- ❌ Annoncer « c'est fait » quand la sortie est ROUGE
- ❌ Demander à Mushine de lancer le script pour voir l'erreur — **lance-le toi-même**
- ❌ Modifier autre chose que ce qui est demandé
- ❌ Supprimer ou désactiver un test pour le faire passer
- ❌ Élargir un seuil ou assouplir un contrôle pour faire disparaître une erreur

### Quand tu bloques

Après **3 tentatives** infructueuses sur la même erreur, arrête-toi et dis :
- ce que tu as essayé, et pourquoi chaque tentative a échoué
- ce qui te manque pour trancher
- les deux ou trois options possibles

Ne pars pas dans une quatrième approche sans le dire.

---

## 3. Ce que tu fais seul / ce qui demande confirmation

### ✅ Sans demander

- lire n'importe quel fichier du projet
- lancer `verif.py`, `pytest`, `constellations.py`, `constellation_agent.py`
- corriger une erreur signalée par `verif.py`
- écrire ou compléter des tests dans `tests/`
- ajouter des commentaires, des docstrings, des annotations de type
- créer un fichier **nouveau** demandé par la tâche en cours

### ⚠️ Demander avant

- modifier un fichier de `gold_agent/` qui touche à la logique de signal
- changer un seuil, un paramètre de décision, une constante de risque
- supprimer un fichier ou renommer un module existant
- ajouter une dépendance externe (`pip install`)
- lancer quoi que ce soit qui appelle une API avec une clé
- toucher à `.env`, à `.git`, ou à quoi que ce soit hors du dossier du projet

### 🛑 Jamais

- écrire du code d'exécution d'ordre (achat/vente réel). **Hors périmètre.**
- écrire une clé API en dur
- committer `.env`
- désactiver un contrôle de `verif.py` pour faire passer du code

---

## 4. Les règles non négociables

### Périmètre
1. Le système **analyse et notifie**. Il ne passe aucun ordre. Aucun code d'exécution n'est écrit tant que Mushine ne le demande pas explicitement.

### Émission de signal
2. Aucune stratégie n'émet sans avoir passé le protocole de backtest (walk-forward, coûts inclus, ≥ 30 trades, ≥ 2 régimes).
3. Aucun couple (instrument × timeframe) ne notifie si son carreau n'est pas VERT dans la grille de conviction.
4. Tout signal respecte le schéma unique `Signal`.
5. Tout signal doit pouvoir dire **qui a voté quoi et avec quel poids**.

### Corrélations
6. **Aucune relation de corrélation n'est écrite en dur.** Toutes sont recalculées sur les données réelles.
7. On corrèle les **rendements**, jamais les prix.
8. Le calendrier est aligné sur les jours de cotation du **pivot** (crypto 7j/7 vs or 5j/7 — c'est le piège n°1).
9. Une corrélation instable ne peut ni confirmer ni contredire.
10. **Des membres corrélés entre eux votent une fois, pas N fois.** Le complexe métaux est une information, pas cinq.

### Calculs
11. La valeur du point vient **toujours** de l'objet `Instrument`. Jamais d'une constante.
12. Une décision utilise un **poids continu**, jamais une étiquette à seuil. Un seuil binaire sur une grandeur continue fait basculer 0,49 et 0,51 dans deux mondes opposés.
13. Une base d'information mince peut **faire douter, jamais rassurer**.
14. Tout backtest inclut spread + slippage + commission + funding.

### Données et code
15. Aucun accès direct à une API : toujours via un adapter de `feeds/`.
16. Aucune clé API dans le code. `.env` uniquement.
17. Aucun fichier ne dépasse 500 lignes.
18. Toute fonction de calcul arrive avec son test dans `tests/`.
19. Un test vérifie un **invariant métier**, pas une valeur numérique. `assert corr == 0.82` casse à la prochaine bougie et ne prouve rien. `assert un_satellite_est_classe_satellite` attrape les vraies régressions.

---

## 5. État actuel du projet

### Ce qui existe et fonctionne

| Fichier | Rôle | État |
|---|---|---|
| `verif.py` | contrôle automatique du projet | ✅ opérationnel |
| `tests/test_constellation.py` | 20 tests du moteur de corrélation | ✅ verts |
| `constellations.py` | exploration des groupes de corrélation (CLI) | ✅ |
| `constellation_agent.py` | AG-09 Constellation + AG-10 Miroir | ✅ |
| `gold_agent/` | le système existant, mono-actif (XAU/USD) | ⚠️ à refactorer |

### Les défauts connus, par priorité

| # | Défaut | Où | Gravité |
|---|---|---|---|
| 1 | `VALEUR_POINT_PAR_LOT = 100.0` en dur | `risk.py`, `notify.py` | 🔴 **le sizing serait faux d'un facteur 100 à 100 000 hors de l'or** |
| 2 | `"XAU/USD"` câblé en dur | `datasource.py`, `backtest.py` | 🟠 bloque le multi-actifs |
| 3 | `web.py` fait 87 Ko | `gold_agent/` | 🟠 à découper |
| 4 | `biais_provisoire()` est un bouche-trou | `constellation_agent.py` | 🟠 à remplacer par AG-02 Structure |
| 5 | `debate.py` utilise des poids choisis à la main | `gold_agent/` | 🟠 doivent être calculés |
| 6 | Twelve Data plafonne à 800 req/jour | `datasource.py` | 🟡 ne scalera pas |

### Ce qu'on a appris des données réelles (07/09/2026)

Ces faits sont **mesurés**, pas supposés. Ils doivent guider le code :

- L'or n'est **pas** principalement piloté par le dollar : DXY à −0,57 mais EUR/USD à seulement +0,18.
- **Tout le forex est découplé de l'or.** Le groupe « devises satellites de l'or » est vide. Le système doit pouvoir afficher un groupe vide plutôt que de le remplir.
- La relation or / taux réels est **trois fois plus faible** que la théorie (−0,27 au lieu de −0,7). L'agent Macro doit rester un agent de contexte.
- L'or se comporte actuellement comme un actif **risk-on** : VIX −0,44, S&P 500 +0,44. Aucune règle « risk-off → or monte » ne doit être écrite.
- Le complexe crypto **se recouple à l'or** : les 8 cryptos dérivent de façon monotone (BTC 0,23 → 0,53 → 0,66). C'est un changement de régime.
- Seuls **l'argent (0,78) et les mineurs (0,72)** ont un poids de confirmation solide.

---

## 6. La feuille de route

Une phase à la fois. On ne passe à la suivante que si `verif.py` est vert.

| Phase | Contenu | Sortie attendue |
|---|---|---|
| **0** | `core/contracts.py` (Instrument, Bar, Signal, AgentMessage). **Corriger le défaut n°1.** Rendre `features/` symbole-agnostique. | tests verts, comportement identique sur XAU/USD |
| **1** | Brancher AG-02 Structure sur le Miroir — remplacer `biais_provisoire()` | le Miroir lit une vraie structure de marché |
| **2** | `research/walkforward.py` + `research/livetest.py` | la grille de conviction a ses premières couleurs |
| **3** | `feeds/` : base, binance, bybit, yahoo | 40+ instruments alimentés |
| **4** | `agents/base.py` + bus + migration des agents en boucles permanentes | tourne 24 h sans intervention |
| **5** | `agents/chef.py` — pondération par score de Brier, recalibration 24 h | les poids bougent seuls |
| **6** | API FastAPI + SSE + interface (4 tuiles → grille → fiche 4 onglets) | l'écran cible |

---

## 7. Le vérificateur

```bash
python3 verif.py            # contrôle complet
python3 verif.py --rapide   # sans les tests (plus rapide pendant l'itération)
python3 verif.py --prompt   # uniquement la liste des choses à corriger
```

Il contrôle : la syntaxe de chaque fichier · le chargement de chaque module (en distinguant une **dépendance manquante** d'une **erreur de code**) · les tests unitaires · les invariants du projet (constantes en dur, symboles câblés, fichiers trop longs, clés API) · le bon fonctionnement des modules de calcul sur données synthétiques.

Il écrit `rapport_verif.md` avec la liste exacte de ce qui reste à corriger.

**Code de sortie : 0 = vert, 1 = rouge.** Tu peux l'enchaîner : `python3 verif.py && echo OK`.

### Si `verif.py` signale quelque chose de faux

Ça arrive — il a déjà eu trois faux positifs pendant sa mise au point. **Ne désactive pas le contrôle.** Signale-le à Mushine avec la ligne concernée et propose une règle plus précise. Un contrôle qui crie au loup finit ignoré, ce qui est pire que pas de contrôle.

---

## 8. Comment ajouter quelque chose

### Un agent

1. Il hérite de `Agent` (`agents/base.py`) : `code`, `nom`, `intervalle`, `async def tick()`
2. Il **publie un avis**, il ne décide jamais d'un signal seul
3. Il ne bloque jamais (aucun appel HTTP synchrone dans la boucle)
4. Il redémarre seul en cas d'erreur, avec backoff exponentiel
5. Il arrive avec ses tests
6. **Question à te poser avant de l'écrire :** quelle information apporte-t-il que les autres n'ont pas ? Si la réponse est floue, ne l'écris pas. Deux agents qui disent la même chose ne valent pas deux confirmations — ils rendent le système plus confiant sans le rendre plus juste.

### Une source de données

1. Elle hérite de `Feed` (`feeds/base.py`)
2. Elle normalise en OHLCV standard
3. Elle a son gestionnaire de rate limit (token bucket) et son backoff
4. Elle a ses tests, avec des réponses figées — **jamais d'appel réseau dans un test**
5. La clé, s'il en faut une, vient de `.env`

### Un test

1. Il vérifie un invariant métier, pas une valeur numérique
2. Il tourne sans réseau, sur données synthétiques
3. Son nom dit ce qu'il protège : `test_une_base_mince_ne_peut_pas_rassurer`
4. S'il corrige un bug, sa docstring dit lequel — c'est ce qui empêche la régression de revenir

---

## 9. Le ton attendu

- Dis ce que tu as fait, pas ce que tu vas faire.
- Si tu n'es pas sûr, dis-le. Une incertitude annoncée coûte moins cher qu'une erreur découverte trois semaines plus tard.
- Si une demande te paraît être une mauvaise idée, dis-le **avant** de l'implémenter, avec la raison.
- Si tu trouves un bug dans ton propre code précédent, signale-le franchement. C'est arrivé plusieurs fois sur ce projet et c'est comme ça qu'il s'est amélioré.
- Ne dis jamais que quelque chose marche si tu ne l'as pas exécuté.

---

## 10. Le pense-bête

```bash
python3 verif.py                       # LA commande. Après chaque changement.
python3 -m pytest tests/ -q            # juste les tests
python3 constellations.py              # constellation de l'or
python3 constellations.py BTC-USD      # constellation du bitcoin
python3 constellation_agent.py         # constellation + verdict intermarché
```

**Avant de dire qu'une tâche est finie, la dernière chose que tu fais est de lancer `python3 verif.py` et de montrer sa sortie.**
