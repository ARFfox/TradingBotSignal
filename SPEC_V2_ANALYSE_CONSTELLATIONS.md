# Spécification v2 — Système d'analyse multi-marchés à constellations

*7 septembre 2026. Ce document remplace la v1 sur deux points : **plus d'exécution automatique** (analyse et signaux seulement) et **ajout du moteur de constellations**, qui devient le cœur du système.*

---

## Ce qui change par rapport à la v1

| | v1 | **v2** |
|---|---|---|
| Exécution | auto en paper puis live | ❌ **supprimée.** Le système analyse, notifie, tu entres à la main. |
| Phase 8-9 | paper trading, live | reportées à plus tard, hors périmètre |
| Concept central | grille de conviction | grille de conviction **+ constellations** |
| Agents | 8 + Chef | **17 + Chef** |
| `execution/` | 4 adapters | remplacé par `journal/` — le suivi virtuel des signaux |

**Ce qui ne change pas et reste obligatoire :** la grille de conviction (un couple actif × timeframe ne notifie que s'il est vert), le protocole de backtest, le contrat de signal, et la correction du bug `VALEUR_POINT_PAR_LOT`.

> ⚠️ Même sans exécution automatique, `risk-engine` reste indispensable : c'est lui qui calcule le **volume à saisir** que le système t'affiche. Et c'est là que vit le bug du point (§ v1). Sans lui, le système te dira « 0,04 lot » sur du Bitcoin en utilisant la formule de l'or.

---

## 1. Le moteur de constellations

### Ce que tu as demandé

> *« Tu peux regrouper les devises qui font les mêmes réactions qu'or, avec la même analyse et la même structure, et qui font le contraire d'or. Je clique sur le groupe et je vois le groupe qui est opposé à l'or, et le groupe qui fait la même réaction. »*

C'est la meilleure idée du projet. C'est de l'analyse intermarché, et c'est exactement comme ça que raisonnent les desks matières premières.

### Une correction importante avant d'aller plus loin

Tu as donné cet exemple : *« si l'or monte, peut-être que EUR/USD descend, donc c'est opposé »*.

**C'est en général l'inverse.** Le raisonnement se fait en deux temps :

1. L'or est coté **en dollars**. Quand le dollar s'affaiblit, l'or monte mécaniquement.
2. L'euro pèse environ **57 % du Dollar Index**. Donc EUR/USD ≈ l'inverse du dollar.

Conclusion : **quand l'or monte, EUR/USD monte aussi le plus souvent** — les deux sont la même idée, « le dollar baisse », exprimée différemment. EUR/USD est un **satellite** de l'or, pas un miroir.

Ce qui baisse vraiment quand l'or monte, ce sont : **le Dollar Index (DXY)**, **USD/CHF**, et surtout **les taux réels américains** (le rendement des TIPS 10 ans) — c'est le moteur fondamental le plus solide de l'or.

Et voilà pourquoi ça compte pour ton système :

> **Si le système avait pris ton hypothèse comme règle en dur, il aurait traité EUR/USD comme une confirmation inverse. Un achat or confirmé par un achat EUR/USD aurait été compté comme une contradiction — donc rejeté. Tu aurais perdu tes meilleurs signaux, et tu ne l'aurais jamais su.**

D'où la règle absolue du moteur :

> **Aucune relation de corrélation n'est écrite en dur. Elles sont toutes recalculées chaque jour sur les données réelles.**

Ce n'est pas de la prudence excessive : les régimes de corrélation **tournent vraiment**. La relation or / USD-JPY, historiquement négative, s'est découplée pendant les cycles de hausse de taux. Un système figé sur les corrélations « connues » se trompe précisément aux moments de rupture — c'est-à-dire quand les mouvements sont les plus grands.

### Le vocabulaire du système

Autour de n'importe quel **pivot** (l'or, le Bitcoin, le SPY, ce que tu veux) :

| Groupe | Condition | Ce que ça veut dire |
|---|---|---|
| 🟢 **SATELLITES** | corr ≥ +0,40 | bougent dans le **même sens** que le pivot |
| ⚪ **DÉCOUPLÉS** | −0,40 < corr < +0,40 | pas de relation exploitable |
| 🔴 **MIROIRS** | corr ≤ −0,40 | bougent en **sens inverse** du pivot |

Chaque membre porte aussi un **score de stabilité** : la corrélation tient-elle sur 30, 90 et 250 jours ? Une corrélation de 0,85 sur 30 jours qui était de −0,10 sur 250 jours **ne vaut rien** — c'est un accident, pas une relation. Le système doit l'afficher comme INSTABLE et refuser de s'en servir comme confirmation.

### Le script est prêt

Le fichier **`constellations.py`** est dans ton dossier. Il ne demande aucune clé API :

```bash
pip3 install yfinance pandas numpy
python3 constellations.py            # constellation de l'or
python3 constellations.py BTC-USD    # constellation du Bitcoin
python3 constellations.py SPY        # constellation du S&P 500
```

Il télécharge 36 actifs sur 3 ans et affiche les satellites, les miroirs et les découplés du pivot, avec les corrélations à 30 / 90 / 250 jours et la stabilité de chacune.

*Je n'ai pas pu l'exécuter d'ici : Yahoo Finance et Binance sont bloqués depuis mon environnement et depuis le bac à sable de ton Mac. Lance-le sur ta machine — les chiffres qui sortiront seront les vrais, à la date d'aujourd'hui, et c'est eux qui doivent alimenter le système, pas une table écrite à la main.*

### Ce que ça donne dans l'interface

Clic sur **XAU/USD** → onglet **Constellation** :

```
CONSTELLATION DE L'OR                     recalculée il y a 3 h · fenêtre 90 j
──────────────────────────────────────────────────────────────────────────────

🟢 SATELLITES — montent quand l'or monte
   ┌──────────────┬──────────────┬──────────────┬──────────────┐
   │ XAG/USD      │ Mineurs GDX  │ EUR/USD      │ AUD/USD      │
   │ corr +0.82   │ corr +0.79   │ corr +0.58   │ corr +0.51   │
   │ stable ✓     │ stable ✓     │ moyenne      │ moyenne      │
   │ 🟢 HAUSSIER  │ 🟢 HAUSSIER  │ 🟢 HAUSSIER  │ ⚪ NEUTRE    │
   │ ✅ confirme  │ ✅ confirme  │ ✅ confirme  │ — neutre     │
   └──────────────┴──────────────┴──────────────┴──────────────┘

🔴 MIROIRS — baissent quand l'or monte
   ┌──────────────┬──────────────┬──────────────┐
   │ DXY          │ Taux réels   │ USD/CHF      │
   │ corr −0.74   │ corr −0.68   │ corr −0.55   │
   │ stable ✓     │ stable ✓     │ moyenne      │
   │ 🔴 BAISSIER  │ 🔴 BAISSIER  │ 🟢 HAUSSIER  │
   │ ✅ confirme  │ ✅ confirme  │ ❌ CONTREDIT │
   └──────────────┴──────────────┴──────────────┘

⚪ DÉCOUPLÉS — aucune relation exploitable en ce moment
   Bitcoin (+0.11, instable) · S&P 500 (−0.04) · Pétrole (+0.19, instable)

──────────────────────────────────────────────────────────────────────────────
VERDICT INTERMARCHÉ    5 confirment · 1 contredit · score 0,71 / 1
                       ✅ La thèse haussière or est soutenue par la structure
                          intermarché. USD/CHF est le seul point de friction —
                          à surveiller, mais sa corrélation n'est que moyenne.
──────────────────────────────────────────────────────────────────────────────
```

**Et le bouton qui compte : `Analyser toute la constellation`.** Il lance l'analyse technique complète (structure, ICT, régime, setup) sur les 12 membres d'un coup, et te montre lesquels offrent le meilleur point d'entrée pour jouer la même idée. Parce que si la thèse « le dollar baisse » est juste, le meilleur R:R n'est pas forcément sur l'or : il est peut-être sur l'argent ou sur les mineurs, qui ont un bêta plus élevé.

---

## 2. Les deux vraies sources d'edge que ça débloque

C'est ici que ton idée cesse d'être une jolie visualisation et devient de la performance.

### A. La confirmation croisée — augmente la probabilité

Un signal isolé sur l'or, c'est une opinion. Le même signal validé par toute la structure intermarché, c'est une thèse.

```
Signal brut          ACHAT XAU/USD H1, confiance 0,62
                              │
                     ┌────────┴────────┐
                     ▼                 ▼
        Satellites haussiers ?   Miroirs baissiers ?
         XAG ✅  GDX ✅  EUR ✅     DXY ✅  Taux ✅  CHF ❌
                     └────────┬────────┘
                              ▼
                  score intermarché 0,71
                              ▼
        Confiance ajustée     0,62 → 0,78   ✅ NOTIFICATION
```

Et le cas inverse, qui est **le plus précieux** :

```
Signal brut          ACHAT XAU/USD H1, confiance 0,68
Structure            DXY monte aussi. Taux réels montent aussi.
                     ▼
                     ⛔ CONTRADICTION MAJEURE
                     L'or monte pendant que le dollar ET les taux montent :
                     le mouvement n'est pas porté par le fondamental.
                     ▼
        Confiance ajustée     0,68 → 0,31   ❌ SIGNAL BLOQUÉ
```

**C'est ce mécanisme qui va le plus réduire tes pertes.** Pas un indicateur de plus : un filtre qui élimine les signaux techniquement jolis mais fondamentalement non soutenus. Ce sont eux qui produisent les séries de pertes.

### B. La divergence de rattrapage — crée des opportunités

Quand deux actifs sont corrélés à +0,82 de façon **stable**, et que l'un bouge sans l'autre, l'écart se referme statistiquement.

```
Sur 5 jours :   Or  +2,4 %        Argent  +0,3 %
Corrélation stable +0,82 sur les 3 fenêtres
Écart normalisé : 2,1 écarts-types  →  au-delà du seuil de 1,8
▼
🎯 OPPORTUNITÉ DE RATTRAPAGE — ACHAT XAG/USD
   L'argent n'a pas suivi l'or. Historiquement, cet écart se referme
   sous 6 jours dans 71 % des cas (sur 43 occurrences depuis 2021).
   Entrée / SL / TP calculés par le Stratège sur XAG/USD.
```

C'est une **famille de setups entièrement nouvelle**, que ton système actuel ne peut pas voir parce qu'il ne regarde qu'un actif à la fois. Et elle a une qualité rare : elle est peu corrélée aux setups techniques classiques, donc elle diversifie réellement.

⚠️ Deux garde-fous obligatoires, sinon c'est un piège :
- **Uniquement sur des paires à corrélation stable** (score ≥ 0,75). Sur une corrélation instable, l'écart ne se referme pas — il s'élargit.
- **Vérifier qu'il n'y a pas de cause spécifique.** Si l'argent ne suit pas parce qu'une news industrielle est sortie, ce n'est pas une divergence, c'est une information. L'agent Vigie doit valider.

---

## 3. La navigation complète

Exactement ce que tu as décrit : chaque actif est un pivot, cliquer dessus ouvre sa famille.

```
NIVEAU 1 — Les marchés
┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
│ 💱 FOREX  │ │ 🪙 CRYPTO │ │ 🥇 MATIÈR.│ │ 📈 ACTIONS│
│ 28 actifs │ │ 30 actifs │ │ 12 actifs │ │ 30 actifs │
│ ●2        │ │ ●3        │ │ ●1        │ │           │
└───────────┘ └───────────┘ └───────────┘ └───────────┘
        │            │
        │            └──► clic CRYPTO ──► grille des 30 carreaux crypto
        │                                  (BTC, ETH, SOL, BNB, XRP…)
        │                                        │
        │                                        └──► clic BTCUSDT
        │                                             ──► fiche Bitcoin
        │                                                 + sa constellation
        │                                                   = toutes les cryptos
        │                                                     classées par
        │                                                     corrélation au BTC
        ▼
NIVEAU 2 — La grille de conviction (ta capture aux 100 carreaux)
┌────────────────────────┐  ┌────────────────────────┐
│ XAUUSD    MATIÈRES ●1  │  │ BTCUSDT     CRYPTO ●2  │
│ +12.4R         ▲ 2,31 %│  │ +8.6R          ▼ 1,04 %│
│ 34 trades · 68 % win   │  │ 27 trades · 63 % win   │
│ PF 1.82 · 18 h moy     │  │ PF 1.54 · 9 h moy      │
└────────────────────────┘  └────────────────────────┘

NIVEAU 3 — La fiche instrument, 4 onglets
  [ Timeframes ]  [ Constellation ]  [ Pourquoi ]  [ Historique ]
       H1/M30/M15/M5      satellites      le vote      les signaux
       côte à côte        et miroirs      des agents   passés et leur
                                                       résultat
```

**Sur le Bitcoin, la constellation est particulièrement utile** : elle te classe les 30 cryptos par corrélation au BTC. Les alts à haute corrélation (> 0,85) ne sont pas des diversifications, ce sont du Bitcoin à effet de levier — le système doit te le dire avant que tu prennes trois positions qui n'en font qu'une. Et celles qui se découplent sont soit une vraie opportunité indépendante, soit un signal d'alerte.

### Les groupes thématiques

En plus des constellations calculées, des groupes nommés — mais **dont l'appartenance est vérifiée par les données**, jamais figée :

`Métaux précieux` · `Anti-dollar` · `Pro-dollar` · `Valeurs refuges` · `Risk-on` · `Devises matières premières` · `Cryptos majeures` · `Alt L1` · `Tech mégacaps` · `Énergie` · `Sensibles aux taux`

Si un actif quitte la définition de son groupe (l'AUD cesse de se comporter comme une devise matière première), le système le signale au lieu de continuer à le classer par habitude. **Ce signalement est lui-même une information de marché** : c'est souvent le début d'un changement de régime.

---

## 4. Les agents — 17 + le Chef

Tu m'as dit d'en ajouter. Une mise en garde d'abord, parce qu'elle détermine si l'ajout aide ou nuit :

> **Deux agents qui disent la même chose ne valent pas deux confirmations.** Si tu ajoutes cinq agents qui regardent tous la tendance sous un angle différent, tu n'obtiens pas cinq avis — tu obtiens un avis compté cinq fois. Le système devient plus confiant sans être plus juste, et c'est exactement comme ça qu'on construit une machine à perdre avec conviction.

Chaque agent ci-dessous a été choisi pour apporter une information que **les autres n'ont pas**. Et le Chef mesure la corrélation entre les avis des agents : deux agents corrélés à plus de 0,8 voient leur poids fusionné automatiquement.

### Les 8 existants (à conserver)

| Code | Agent | Rôle | Évolution v2 |
|---|---|---|---|
| AG-01 | **Vigie** | news éco, géo, macro | + GDELT (presse mondiale toutes les 15 min, gratuit) |
| AG-02 | **Structure** | analyse graphique 5 TF | rendu multi-actifs |
| AG-03 | **Stratège** | règles + filtres | rendu multi-actifs |
| AG-04 | **Traceur** | zones, ABC, Fibonacci | rendu multi-actifs |
| AG-05 | **Minières & Flux** | COT, positionnement | + funding, open interest, ratio long/short (gratuit chez Binance) |
| AG-06 | Probabilité | espérances | → **fusionné dans le Chef** |
| AG-07 | Opportunités | classement R:R | → **fusionné dans le Chef** |
| AG-00 | Superviseur | synthèse | → **devient le Chef d'orchestre** |

### Les 9 nouveaux

| Code | Agent | Ce qu'il apporte que personne d'autre n'a | Impact |
|---|---|---|---|
| **AG-09** | 🌐 **Constellation** | Recalcule chaque jour les corrélations glissantes 30/90/250 j, la stabilité, l'appartenance aux groupes, et signale les ruptures de régime. | 🔴 structurant |
| **AG-10** | 🪞 **Miroir** | La confirmation croisée du §2A : le signal du pivot est-il soutenu par ses satellites et contredit par ses miroirs ? Ajuste la confiance à la hausse ou à la baisse. | 🔴 **le plus fort réducteur de pertes** |
| **AG-16** | 😈 **Avocat du diable** | Cherche **activement** les raisons pour lesquelles le setup va échouer : niveau majeur contraire proche, liquidité au-dessus du TP, news dans la fenêtre, setup déjà échoué 3 fois ce mois-ci, régime défavorable. Vote toujours CONTRE et doit être réfuté. | 🔴 **le second** |
| **AG-13** | 🏛️ **Macro & taux réels** | DFII10, courbe des taux, DXY, points morts d'inflation. C'est le moteur fondamental de l'or, et rien dans ton système actuel ne le lit. | 🟠 fort |
| **AG-11** | 🕐 **Sessions** | Comportement par session (Asie / Londres / New York), volatilité par heure, plages horaires où **ce setup précis** a historiquement fonctionné. L'or et le forex ont des signatures horaires très marquées. | 🟠 fort |
| **AG-12** | 📏 **Volatilité & liquidité** | Régime d'ATR, élargissement du spread, mouvement attendu à l'horizon du trade. Empêche d'entrer quand le SL est mécaniquement trop proche du bruit. | 🟠 fort |
| **AG-15** | 🧠 **Analogues** | Trouve les configurations historiquement semblables et rapporte ce qui s'est passé ensuite : *« cette configuration s'est produite 47 fois depuis 2019 ; +1,2R en moyenne, 64 % de réussite, échec surtout en régime de compression »*. | 🟠 fort |
| **AG-17** | 🎯 **Rattrapage** | Détecte les divergences du §2B entre actifs à corrélation stable et propose le trade de convergence. Famille de setups entièrement nouvelle. | 🟡 différenciant |
| **AG-14** | 📅 **Saisonnalité** | Effets jour de semaine, mois, heure. Modeste seul, mais utile en départage quand deux setups se valent. | 🟡 secondaire |

### Le Chef d'orchestre — AG-00

Il fusionne Probabilité + Opportunités + Superviseur. Cinq responsabilités :

**1. Collecter** les avis des 17 agents par (instrument × timeframe).

**2. Pondérer par la performance mesurée.** C'est le point décisif. Aujourd'hui ton `debate.py` utilise des poids choisis à la main — c'est le maillon faible de tout le système. Le Chef calcule le **score de Brier** de chaque agent sur ses 100 derniers avis **résolus**, séparément pour chaque couple (instrument, timeframe) :

> Un agent qui a eu raison 68 % du temps sur l'or en H1 pèse lourd. Le même agent à 47 % sur EUR/USD en M5 pèse presque rien. **Les poids sont calculés, jamais choisis.**

C'est la seule chose qui transforme « 17 agents qui donnent leur avis » en un système qui apprend.

**3. Décider de notifier — 6 conditions cumulatives :**

```
1. Le carreau (instrument × tf) est VERT dans la grille de conviction
2. Confluence pondérée ≥ 0,65
3. Au moins 3 agents INDÉPENDANTS d'accord (corrélation entre eux < 0,7)
4. R:R ≥ 1,5 après coûts réels (spread + slippage + commission + funding)
5. Score intermarché du Miroir ≥ 0,50           ← nouveau en v2
6. L'Avocat du diable a été réfuté               ← nouveau en v2
```

Une seule condition qui saute → **rien**. Pas de « signal faible », pas de « à surveiller ».

**4. Superviser** : heartbeats, taux d'erreur, dérive de performance. Un agent mort ou dont le score passe sous le seuil est exclu du vote et signalé dans l'interface.

**5. Arbitrer** : quand plusieurs signaux valides apparaissent, garder les meilleurs **et non corrélés entre eux** — l'agent Constellation dit lesquels sont redondants.

**Recalibration toutes les 24 h :** résoudre les avis échus, recalculer les scores de Brier, mettre à jour les poids et les couleurs de la grille, recalculer les constellations, écrire un rapport lisible.

---

## 5. Le rythme du système

Tu voulais « chaque seconde ». Voici la version qui marche vraiment, avec l'ajout v2.

| Couche | Fréquence | Contenu |
|---|---|---|
| **Prix** | temps réel (WebSocket) | ticks poussés par Binance, zéro polling |
| **Déclencheur** | **chaque seconde** | entrée touchée ? invalidation franchie ? signal expiré ? |
| **Analyse** | clôture de bougie + si mouvement > 0,3 ATR | structure, indicateurs, ICT, régime, setup |
| **Miroir** | **à chaque nouveau signal** | confirmation croisée sur toute la constellation |
| **Contexte** | 60 s | news GDELT, calendrier, funding, OI, ratio L/S |
| **Constellations** | **6 h** | corrélations glissantes, stabilité, ruptures de régime |
| **Calibration** | **24 h** | scores de Brier, poids des agents, couleurs de la grille |

Recalculer la structure H1 chaque seconde produit 3 600 fois le même résultat et pousse le système à réagir au bruit intra-bougie — c'est la première cause d'entrées prématurées. Cette architecture-là est vivante à la seconde là où ça compte, sans réanalyser du vide.

---

## 6. Les skills — 14

Les 12 de la v1, moins `execution-broker`, plus trois nouvelles.

### Inchangées et prioritaires
`signal-contract` · `backtest-protocol` · `market-data-adapter` · `risk-engine` *(garde tout son sens : il calcule le volume affiché)* · `agent-loop` · `confluence-scoring` · `live-testing-grid` · `market-regime` · `ict-smc-analysis` · `news-impact-scoring` · `notification-router`

### ⭐ Nouvelles en v2

**`correlation-clusters`** — le moteur de constellations
- Corrélation des **log-rendements**, jamais des prix
- Fenêtres 30 / 90 / 250 jours, calcul du score de stabilité
- Seuils satellite +0,40 / miroir −0,40, échantillon minimum 60 % de données valides
- Test de significativité : une corrélation sur 30 points n'est pas une corrélation
- Détection des ruptures de régime, et alerte quand un actif quitte son groupe
- **Règle : aucune relation en dur. Jamais.**

**`intermarket-confirmation`** — l'agent Miroir
- Comment un signal de pivot est confirmé ou contredit par sa constellation
- Formule d'ajustement de confiance, pondérée par la stabilité de chaque corrélation
- Seuil de blocage : contradiction sur un miroir **stable** = signal rejeté
- Une corrélation instable ne peut **ni** confirmer **ni** contredire

**`devils-advocate`** — l'Avocat du diable
- Liste exhaustive de ce qu'il doit chercher : niveau majeur contraire à moins de 1 ATR, poche de liquidité avant le TP, news à fort impact dans la fenêtre du trade, ce setup a échoué N fois ce mois-ci, régime défavorable, corrélation avec une position déjà ouverte, spread anormal, volume en baisse sur la cassure
- Format de son objection et **critère de réfutation** : ce qu'il faut pour passer outre
- **Il vote toujours CONTRE.** C'est son métier. Sa valeur est de forcer les autres à être meilleurs.

### Le `CLAUDE.md` v2

```markdown
# Règles du projet — non négociables

## Périmètre
1. Le système ANALYSE et NOTIFIE. Il ne passe aucun ordre. Aucun code
   d'exécution n'est écrit tant que je ne l'ai pas demandé explicitement.

## Émission de signal
2. Aucune stratégie n'émet sans avoir passé `backtest-protocol`.
3. Aucun couple (instrument × tf) ne notifie si son carreau n'est pas VERT.
4. Les 6 conditions du Chef d'orchestre sont cumulatives. Aucune exception.
5. Tout signal respecte le schéma `signal-contract`.
6. Tout signal doit pouvoir dire QUI a voté quoi et avec quel poids.

## Corrélations
7. Aucune relation de corrélation n'est écrite en dur. Elles sont TOUTES
   recalculées sur données réelles, toutes les 6 heures.
8. Une corrélation instable (score < 0,50) ne peut ni confirmer ni contredire.
9. Deux positions corrélées à plus de 0,7 comptent comme une seule.

## Données
10. Aucun accès direct à une API : toujours via un adapter de `feeds/`.
11. Toute nouvelle source arrive avec ses tests et son rate limiter.
12. Aucune clé API dans le code. `.env` uniquement.

## Calculs
13. La valeur du point vient TOUJOURS de l'objet Instrument. Jamais d'une
    constante. (Bug actuel : VALEUR_POINT_PAR_LOT = 100.0 dans risk.py
    ET dans notify.py — faux partout sauf sur l'or.)
14. On corrèle les rendements, jamais les prix.
15. Tout backtest inclut spread + slippage + commission + funding.

## Code
16. Aucun fichier ne dépasse 500 lignes.
17. Les poids des agents sont calculés, jamais choisis à la main.
```

---

## 7. Le plan révisé

| Phase | Contenu | Durée | Critère de sortie |
|---|---|---|---|
| **0** | `CLAUDE.md`, skills prioritaires, `core/contracts.py`, `feeds/base.py`. **Corriger `VALEUR_POINT_PAR_LOT`.** Rendre `features/` symbole-agnostique. | 2-3 j | Tests verts, comportement identique sur XAU/USD |
| **1** | ⭐ **Lancer `constellations.py`.** Puis `agents/constellation.py` (AG-09) sur données réelles. | 2 j | Tu connais les vrais groupes, avec leur stabilité |
| **2** | `research/walkforward.py` + `research/livetest.py`. Rejouer la stratégie sur 20 instruments × 4 TF, coûts inclus. | 4-5 j | La grille a ses premières couleurs |
| **3** | Adapters Binance (REST + WS), Bybit, yfinance. | 3-4 j | 42 instruments alimentés en continu |
| **4** | `core/bus.py`, `agents/base.py`, migration des 8 agents en boucles permanentes. | 4-5 j | Tourne 24 h sans intervention, heartbeats verts |
| **5** | ⭐ **AG-10 Miroir + AG-16 Avocat du diable.** Les deux plus gros réducteurs de pertes. | 3 j | Les signaux contredits par l'intermarché sont bloqués |
| **6** | AG-13 Macro, AG-11 Sessions, AG-12 Volatilité, AG-15 Analogues. | 4 j | 4 sources d'information nouvelles et indépendantes |
| **7** | `agents/chef.py` — fusion, pondération par Brier, recalibration 24 h. | 4 j | Les poids bougent seuls, rapport quotidien lisible |
| **8** | `decision/router.py` + notifications ntfy + journal unifié. | 2 j | Une seule source de vérité pour pastille et téléphone |
| **9** | Interface : 4 tuiles → grille → fiche 4 onglets (Timeframes / Constellation / Pourquoi / Historique). | 5-6 j | ⭐ Ton écran cible |
| **10** | Adapters forex (Dukascopy) + actions (Alpaca, Finnhub, SEC). AG-17 Rattrapage, AG-14 Saisonnalité. | 4 j | 100 instruments |
| — | *Exécution automatique* | — | *hors périmètre pour l'instant* |

---

## 8. Les prompts

### Phase 1 — les constellations (commence ici, c'est le plus motivant)

```
Lance d'abord constellations.py à la racine du projet et montre-moi la sortie.

Puis crée agents/constellation.py (AG-09) :
- corrélation des log-rendements sur fenêtres glissantes 30 / 90 / 250 jours
- score de stabilité = 1 - (écart-type des 3 fenêtres / 0.35), borné 0-1
- classement : SATELLITES (corr >= +0.40), MIROIRS (corr <= -0.40),
  DECOUPLES entre les deux
- test de significativité : rejeter toute corrélation calculée sur moins de
  60 % de données valides sur la fenêtre
- détection de rupture de régime : alerter quand la corrélation 30 j s'écarte
  de plus de 0,4 de la corrélation 250 j
- groupes thématiques nommés, mais dont l'appartenance est VÉRIFIÉE par les
  données à chaque recalcul, jamais figée
- recalcul toutes les 6 h, résultat persisté
- API : constellation(pivot) -> {satellites, miroirs, decouples}
        avec pour chaque membre : corr, stabilite, biais_actuel

RÈGLE ABSOLUE : aucune relation de corrélation écrite en dur dans le code.
Tout vient des données. Les régimes de corrélation changent.
```

### Phase 5 — les deux agents qui réduisent le plus les pertes

```
Crée agents/miroir.py (AG-10).

Quand un signal apparaît sur un pivot :
1. Récupérer sa constellation via AG-09
2. Pour chaque satellite : son biais actuel confirme-t-il le signal ?
3. Pour chaque miroir : son biais actuel est-il bien opposé ?
4. Score intermarché = somme pondérée par (|corr| × stabilite) des
   confirmations, divisée par la somme des poids
5. Ajuster la confiance du signal en fonction de ce score
6. BLOQUER le signal si un miroir STABLE (stabilite >= 0.75) va dans le
   même sens que le pivot — c'est une contradiction majeure

Une corrélation instable (stabilite < 0.50) ne peut NI confirmer NI contredire :
elle est ignorée dans le calcul, et signalée comme ignorée dans le rapport.

Puis crée agents/avocat_du_diable.py (AG-16). Il vote TOUJOURS contre et
cherche activement :
- un niveau majeur contraire à moins de 1 ATR de l'entrée
- une poche de liquidité entre l'entrée et le TP1
- une news à fort impact dans la fenêtre de vie du trade
- ce setup a déjà échoué N fois ce mois-ci sur cet instrument
- le régime actuel est défavorable à ce type de setup
- le spread est anormalement large
- le volume baisse sur la cassure

Il produit une objection structurée avec un critère de réfutation explicite.
Le Chef ne peut émettre que si l'objection est réfutée.
```

---

## 9. Ce que je te recommande de faire ce soir

1. **Lance `constellations.py`** sur ton Mac. C'est 2 minutes, aucune clé, et tu vas voir les vrais groupes de l'or avec les vrais chiffres d'aujourd'hui. Envoie-moi la sortie.
2. Ensuite **Phase 0** — le refactor, et surtout la correction de `VALEUR_POINT_PAR_LOT`.
3. Puis **Phase 2**, le walk-forward, qui donnera ses premières couleurs à ta grille.

Les constellations d'abord parce que c'est visuel, immédiat, et que ça va probablement te surprendre — les corrélations réelles ne sont presque jamais celles qu'on croit. Et parce que tout le reste du système va s'appuyer dessus.
