# Système de trading multi-marchés autonome — spécification complète

*Rédigé le 7 septembre 2026, après lecture du code de `~/Trading Claude/gold_agent`.*
*Document de référence : à garder à la racine du projet et à donner à Claude Code au début de chaque session.*

---

## Sommaire

1. [État des lieux du code existant](#1-état-des-lieux)
2. [Le concept central : la grille de conviction](#2-le-concept-central)
3. [L'écran cible, carreau par carreau](#3-lécran-cible)
4. [La fiche instrument multi-timeframes](#4-la-fiche-instrument)
5. [Architecture technique](#5-architecture-technique)
6. [Les agents autonomes : ce que « réfléchir en permanence » veut vraiment dire](#6-les-agents-autonomes)
7. [Le Chef d'orchestre : l'agent qui supervise les agents](#7-le-chef-dorchestre)
8. [Les 12 skills Claude Code](#8-les-12-skills)
9. [Les APIs — toutes gratuites](#9-les-apis)
10. [Le plan par phases](#10-le-plan-par-phases)
11. [Les prompts prêts à coller](#11-les-prompts)
12. [Les 6 pièges qui tuent ce genre de système](#12-les-pièges)

---

## 1. État des lieux

### Ce qui est déjà bon

| Fichier | Ce qu'il fait | Verdict |
|---|---|---|
| `datasource.py` | Twelve Data avec **rotation automatique de clés**, TTL adaptatif, backoff | Vraie ingénierie. À conserver comme source d'appoint. |
| `config.py` | L'émission est limitée à H4/H1/M30 **parce que le backtest le dit** (M15 à +0,06R coupé, M5 à 17 jours de données coupé) | 🏆 **La meilleure décision du projet.** Tout le reste doit s'aligner sur ce principe. |
| `strategy.py` | `detecter()` → `simuler()` → `statistiques()` : la boucle signal → trade → mesure existe déjà | Le squelette du moteur est là |
| `indicators.py` `structure.py` `ict.py` `patterns.py` `regime.py` | EMA, RSI, ATR, ADX, MACD, Bollinger, stochastique, pivots, FVG, divergences, régime de volatilité | Couche analyse riche et déjà écrite |
| `debate.py` | Consensus pondéré entre agents | La bonne intuition, mal calibrée (voir §7) |
| `journal.py` | Anti-rafale 12 h, résolution des signaux, abandon après 48 h | Détails de production bien pensés |
| `notify.py` | ntfy vers le téléphone + notification système | Le canal existe déjà |

### Les 6 blocages structurels

| # | Blocage | Preuve dans le code | Conséquence |
|---|---|---|---|
| 1 | **XAU/USD est câblé en dur** | `def twelvedata_bars(symbole: str = "XAU/USD", ...)` | Aucun réglage par actif possible |
| 2 | **La valeur du point est en dur** | `VALEUR_POINT_PAR_LOT = 100.0` dans `risk.py` **et** dans `notify.py` | ⚠️ **Sur BTC ou EURUSD, le sizing sera faux d'un facteur 100 à 100 000.** C'est le bug qui vide un compte. |
| 3 | **`web.py` fait 87 Ko** | HTTP + HTML + métier dans un seul fichier | Claude Code va s'y perdre, chaque ajout coûte plus cher que le précédent |
| 4 | **Twelve Data ne scalera jamais** | 800 requêtes/jour/clé | 100 actifs × 4 TF × rafraîchissement 5 min = **115 200 req/jour**. Ajouter des clés ne résout rien. |
| 5 | **Les agents ne sont pas des processus** | Ce sont des fonctions appelées au rendu de la page | « Toujours en ligne, réfléchit toujours » n'existe pas encore |
| 6 | **`TF_EMISSION_DEFAUT` est une liste globale** | `["H4", "H1", "M30"]` pour tout | Or le M5 peut être excellent sur BTC et catastrophique sur EURUSD. Il faut une décision **par couple (actif × timeframe)**. |

### Le point le plus important

Ta capture affiche `journal réel : 0.0%` et `1 setup`. Le système n'a pas encore la preuve qu'il gagne sur **un seul** marché.

La capture que tu m'as montrée (« Live Testing 100+ assets ») contient la réponse à ça, et c'est pour ça que c'est la bonne direction : dans cette grille, **la majorité des carreaux sont négatifs**. C'est normal, et c'est exactement l'information qui a de la valeur. Un système qui teste 100 actifs et n'en garde que les 15 verts gagne. Un système qui trade les 100 perd.

**La grille n'est pas un tableau de bord décoratif. C'est le mécanisme de sélection.**

---

## 2. Le concept central

> **Un actif n'a pas le droit d'émettre un signal live tant que son carreau n'est pas vert.**

C'est la généralisation directe de ce que fait déjà ton `config.py`, mais appliquée à chaque couple (instrument × timeframe) au lieu d'une liste globale.

```
100+ instruments × 4 timeframes  =  400+ combinaisons testées en continu
            │
            ├─ walk-forward sur historique (edge théorique, coûts inclus)
            ├─ live testing en paper (edge réel, exécution incluse)
            │
            ▼
   ┌────────────────────────────────────────────┐
   │  VERT   R > +0.3, PF > 1.3, ≥30 trades     │ → émet en live + notification
   │  BLEU   edge positif mais échantillon court│ → observe, pas de notification
   │  GRIS   neutre                             │ → observe
   │  ROUGE  R < 0                              │ → muet, mais continue d'être testé
   └────────────────────────────────────────────┘
```

Le carreau change de couleur tout seul, en continu, à mesure que les trades se résolvent. Un actif qui était vert et se dégrade repasse au rouge et se coupe **sans que tu interviennes**. C'est ça, un système qui s'auto-régule.

**Métriques affichées sur chaque carreau** (identiques à ta capture, plus la variation de prix que tu as demandée) :

| Champ | Exemple | Source |
|---|---|---|
| Symbole | `BTCUSDT` | instrument |
| Marché | `CRYPTO` | instrument |
| **R cumulé** | `+12.4R` | somme des R des trades résolus |
| **Variation prix** | `▲ 2,31 %` | (close − close_24h) / close_24h |
| Nb de trades | `34 trades` | journal |
| Taux de réussite | `68 % win` | journal |
| Profit factor | `PF 1.82` | somme gains / somme pertes |
| Durée moyenne | `18 h moy` | journal |
| **Pastille** | `● 2` | nb de signaux actifs non expirés |

---

## 3. L'écran cible

### Niveau 1 — Les 4 marchés

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  💱 FOREX    │ │ 🪙 CRYPTO ●3 │ │ 🥇 MATIÈRES  │ │ 📈 ACTIONS ●1│
│  28 actifs   │ │  30 actifs   │ │  12 actifs   │ │  30 actifs   │
│  +34.2R      │ │  +58.7R      │ │  +21.4R      │ │  −4.1R       │
│  11 verts    │ │  14 verts    │ │  5 verts     │ │  3 verts     │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

La pastille rouge `●3` = 3 opportunités actives de confiance ≥ seuil dans ce marché.

### Niveau 2 — La grille de conviction

Clic sur un marché → la grille de ta capture, triée par R décroissant.

```
┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐
│ BTCUSDT     CRYPTO ●2 │  │ SOLUSDT     CRYPTO    │  │ XAUUSD    MATIÈRES ●1 │
│ +12.4R        ▲ 2,31% │  │ +8.6R         ▼ 1,04% │  │ +7.9R        ▲ 0,42%  │
│ 34 trades · 68 % win  │  │ 27 trades · 63 % win  │  │ 41 trades · 59 % win  │
│ PF 1.82 · 18 h moy    │  │ PF 1.54 · 9 h moy     │  │ PF 1.47 · 26 h moy    │
└───────────────────────┘  └───────────────────────┘  └───────────────────────┘
     vert vif                    vert                       vert
```

Dégradé de couleur : vert vif (R > +8) → vert → bleu → gris → rouge (R < −2). Exactement ta capture.

**Filtres en haut de grille :** `Tous` · `Verts seulement` · `Signal actif` · trier par R / PF / variation / nb de trades.

### Niveau 3 — La fiche instrument

Clic sur un carreau → §4.

---

## 4. La fiche instrument

C'est ce que tu as demandé : **toutes les timeframes visibles d'un coup**.

```
BTCUSDT · CRYPTO                              109 842,50   ▲ 2,31 % (24 h)
Edge global +12.4R · 34 trades · 68 % · PF 1.82        [ ● 2 signaux actifs ]
──────────────────────────────────────────────────────────────────────────────

           H1                M30               M15               M5
        ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
Statut  │ 🟢 ACTIF │     │ 🟢 ACTIF │     │ 🔵 OBS.  │     │ 🔴 MUET  │
Edge    │  +6.1R   │     │  +4.8R   │     │  +1.5R   │     │  −0.9R   │
        │  PF 1.9  │     │  PF 1.6  │     │  PF 1.1  │     │  PF 0.8  │
        │ 18t·72%  │     │ 24t·66%  │     │ 11t·54%  │     │ 31t·41%  │
        ├──────────┤     ├──────────┤     ├──────────┤     ├──────────┤
Biais   │ HAUSSIER │     │ HAUSSIER │     │  NEUTRE  │     │ BAISSIER │
Régime  │ tendance │     │ tendance │     │  range   │     │  range   │
        ├──────────┤     ├──────────┤     ├──────────┤     ├──────────┤
SETUP   │ ACHAT    │     │ ACHAT    │     │    —     │     │    —     │
Entrée  │ 109 420  │     │ 109 680  │     │          │     │          │
SL      │ 108 150  │     │ 109 100  │     │          │     │          │
TP1     │ 111 200  │     │ 110 400  │     │          │     │          │
TP2     │ 112 800  │     │ 111 100  │     │          │     │          │
R:R     │  1 : 2,4 │     │  1 : 1,8 │     │          │     │          │
Conf.   │   78 %   │     │   64 %   │     │          │     │          │
Volume  │ 0,042 BTC│     │ 0,031 BTC│     │          │     │          │
Expire  │  dans 9h │     │ dans 4h  │     │          │     │          │
        └──────────┘     └──────────┘     └──────────┘     └──────────┘

POURQUOI (H1, confiance 78 %)
  ✅ Structure   BOS haussier confirmé, HH/HL depuis 14 bougies        poids 0,22
  ✅ Stratège    pullback sur EMA50 + order block H4 non mitigé        poids 0,19
  ✅ Flux        funding +0,011 % · OI +8,4 % · ratio L/S 1,34         poids 0,17
  ✅ Traceur     Fibonacci 61,8 % de la jambe C, confluence FVG        poids 0,14
  ⚠️  Vigie      FOMC dans 31 h — fenêtre de blocage à T−4 h           poids 0,12
  ❌ Probabilité base historique de ce setup : 61 % (sous la moyenne)  poids 0,16

INVALIDATION   clôture H1 sous 108 150, ou funding > +0,05 %
CORRÉLATION    ⚠️ position ETHUSDT déjà ouverte, corr. 0,87 — taille réduite de 40 %
```

**Le bloc « POURQUOI » est non négociable.** Un système autonome que tu ne peux pas auditer est un système que tu couperas à la première série de pertes — au pire moment, statistiquement. Chaque signal doit dire qui a voté quoi, avec quel poids, et le poids doit venir de la performance mesurée de cet agent (§7).

---

## 5. Architecture technique

```
trading_system/
├── CLAUDE.md                    # règles non négociables, lues à chaque session
├── .claude/skills/              # les 12 skills (§8)
│
├── core/
│   ├── contracts.py             # Instrument, Bar, Signal, AgentMessage, Verdict
│   ├── bus.py                   # bus asyncio pub/sub (upgradeable Redis)
│   ├── store.py                 # DuckDB : barres, signaux, trades, métriques agents
│   └── clock.py                 # sessions, horaires marché, bougies en cours
│
├── feeds/                       # 1 fichier par source, TOUS le même contrat
│   ├── base.py                  # Feed : fetch_ohlcv, stream, token bucket, cache
│   ├── binance.py               # crypto REST+WS + funding + OI + ratio L/S
│   ├── bybit.py                 # redondance crypto
│   ├── yahoo.py                 # forex, matières premières, actions (historique)
│   ├── twelvedata.py            # existant, rétrogradé en appoint
│   ├── dukascopy.py             # tick data forex historique (backtest)
│   ├── alpaca.py                # actions temps réel + paper
│   ├── fred.py  cot.py  gdelt.py  finnhub.py  sec.py
│
├── features/                    # ← ton code actuel, rendu symbole-agnostique
│   └── indicators.py  structure.py  ict.py  patterns.py  regime.py
│
├── agents/
│   ├── base.py                  # Agent : run(), heartbeat, état, reprise sur crash
│   ├── vigie.py                 # AG-01 news éco + géo + macro
│   ├── structure.py             # AG-02 analyse graphique multi-TF
│   ├── strategie.py             # AG-03 règles + filtres
│   ├── traceur.py               # AG-04 zones, ABC, Fibonacci
│   ├── flux.py                  # AG-05 COT + funding + OI + ratio L/S
│   ├── correlation.py           # AG-09 ⭐ NOUVEAU — indispensable en multi-marchés
│   └── chef.py                  # AG-00 ⭐ Probabilité + Opportunité + Superviseur (§7)
│
├── decision/
│   ├── confluence.py            # fusion pondérée par performance mesurée
│   ├── risk.py                  # sizing, exposition, corrélation, kill switch
│   └── router.py                # règles de notification et de pastille
│
├── execution/
│   ├── base.py                  # interface Broker
│   └── paper.py  binance_ex.py  metaapi_ex.py  alpaca_ex.py
│
├── research/
│   ├── walkforward.py           # ⭐ LE module qui décide qui a le droit d'émettre
│   ├── livetest.py              # ⭐ le moteur de la grille de conviction
│   └── metrics.py
│
├── api/                         # FastAPI + SSE (remplace web.py)
└── ui/                          # 4 tuiles → grille → fiche multi-TF
```

**Le principe qui tient tout :** un `Signal` a exactement le même schéma qu'il vienne du Bitcoin, de l'EUR/USD, de l'or ou de Nvidia. Toute la logique en aval — risque, notification, journal, backtest, grille — devient marché-agnostique et tu l'écris **une seule fois**.

### L'univers d'actifs (~100, comme ta capture)

| Marché | Nombre | Contenu |
|---|---|---|
| **Forex** | 28 | 7 majeures + 21 crosses (EURJPY, GBPJPY, AUDNZD, EURAUD…) |
| **Crypto** | 30 | BTC, ETH, SOL, BNB, XRP, ADA, AVAX, LINK, DOT… (top capitalisation, paires USDT) |
| **Matières premières** | 12 | XAU, XAG, WTI, Brent, cuivre, gaz naturel, platine, palladium, blé, maïs, soja, sucre |
| **Actions** | 30 | 7 mégacaps + SPY, QQQ, IWM + 20 forte capitalisation à news |

**Total ≈ 100.** Au-delà, le bruit croît plus vite que le signal et tu ne peux plus auditer.

---

## 6. Les agents autonomes

Tu as écrit : *« je veux que les agents fassent toujours l'analyse à chaque seconde »*.

Je te donne la version honnête, parce que la version naïve détruit la qualité des signaux.

### Pourquoi « recalculer tout chaque seconde » est une mauvaise idée

Une bougie H1 ne change pas de nature entre la seconde 12 et la seconde 13. Recalculer la structure H1 chaque seconde produit **le même résultat 3 600 fois de suite**, brûle du CPU, et surtout : ça pousse le système à réagir à du bruit intra-bougie. C'est la cause n°1 des sur-signaux et des entrées prématurées.

### Ce qu'il faut faire à la place : 4 couches à 4 fréquences

| Couche | Fréquence | Ce qu'elle fait | Coût |
|---|---|---|---|
| **Prix** | **temps réel (WebSocket)** | Reçoit chaque tick poussé par Binance. Aucun polling. | ~0 |
| **Déclencheur** | **chaque seconde** | Sur chaque signal actif : l'entrée limite est-elle touchée ? le SL est-il touché ? l'invalidation est-elle franchie ? le signal a-t-il expiré ? | très faible |
| **Analyse** | **à la clôture de bougie** + si le prix bouge de > 0,3 ATR | Recalcule structure, indicateurs, ICT, régime, setup. M5 → toutes les 5 min, H1 → toutes les heures. | modéré |
| **Contexte** | **toutes les 60 s** | News GDELT, calendrier éco, funding, open interest, ratio long/short, corrélations | faible |

Résultat : **le système est vivant à la seconde** (il réagit instantanément à un prix qui touche ton entrée ou ton stop) **sans réanalyser du bruit**. C'est exactement ce que font les desks professionnels.

### Le contrat d'un agent permanent

```python
class Agent:
    code: str              # "AG-01"
    nom: str               # "Vigie"
    intervalle: float      # sa fréquence propre, en secondes
    
    async def run(self):
        while True:
            try:
                await self.tick()               # son travail
                self.heartbeat = now()          # preuve qu'il est vivant
                self.erreurs_consecutives = 0
            except Exception as e:
                self.erreurs_consecutives += 1
                self.log(e)
                await sleep(backoff(self.erreurs_consecutives))  # 2,4,8,16... max 300s
                continue
            await sleep(self.intervalle)
    
    async def tick(self):
        """Produit un AgentMessage et le publie sur le bus. Jamais bloquant."""
```

**Règles non négociables :**
- Un agent qui plante **redémarre seul** avec backoff exponentiel — il ne fait jamais tomber les autres
- Un agent sans heartbeat depuis 3 × son intervalle est déclaré **mort** et le Chef d'orchestre l'exclut du vote
- Un agent ne bloque jamais (aucun appel HTTP synchrone dans la boucle)
- Un agent ne décide jamais d'un trade seul : il **publie un avis**, le Chef tranche

---

## 7. Le Chef d'orchestre

C'est le point que tu as très bien vu : *« l'agent qui fait la probabilité et l'opportunité travaille avec tous les agents et supervise tous les agents »*.

Aujourd'hui tu as trois agents séparés — Probabilité (AG-06), Opportunités (AG-07), Superviseur (AG-00) — qui font en réalité **un seul métier en trois morceaux**. Il faut les fusionner en un **Chef d'orchestre**.

### Ses 5 responsabilités

**1. Collecter les avis.** Chaque agent publie un `AgentMessage` : direction, force (0-1), horizon, raison, horodatage. Le Chef les rassemble par (instrument × timeframe).

**2. Pondérer par la performance mesurée — et c'est ici que tout se joue.**

Aujourd'hui ton `debate.py` pondère avec des coefficients choisis à la main. C'est le maillon faible. Le Chef doit calculer, pour chaque agent, **le taux de réussite de ses avis passés sur cet instrument et ce timeframe** :

```
poids(agent, instrument, tf) = f(brier_score des 100 derniers avis résolus)
```

Un agent dont les avis se sont vérifiés à 68 % sur BTC en H1 pèse lourd. Le même agent à 47 % sur EURUSD en M5 pèse presque rien. **Les poids sont calculés, jamais choisis.** Et ils sont différents pour chaque couple (instrument × TF).

C'est la seule chose qui transforme « 8 agents qui donnent leur avis » en « un système qui apprend ».

**3. Décider d'émettre — 5 conditions cumulatives, toutes obligatoires :**

```
1. Le carreau (instrument × tf) est VERT dans la grille de conviction
2. Confluence pondérée ≥ 0,65
3. Au moins 3 agents indépendants d'accord (pas 3 variantes du même indicateur)
4. R:R ≥ 1,5 après coûts réels (spread + slippage + commission + funding)
5. Le filtre risque passe : exposition, corrélation, fenêtre de news, kill switch
```

Une seule condition qui saute → **pas de signal**. Pas de « signal faible », pas de « à surveiller ». Rien.

**4. Superviser les agents.** Heartbeats, taux d'erreur, dérive de performance. Un agent dont le score se dégrade est automatiquement déclassé, puis exclu du vote. Le Chef le signale dans l'interface — c'est ce que ton Superviseur fait déjà, en mieux.

**5. Arbitrer entre instruments.** Quand 6 signaux valides apparaissent en même temps, il n'en garde que 2 ou 3 : les meilleurs R:R × confiance, **et non corrélés entre eux**. C'est ce qui empêche d'ouvrir 4 positions qui sont en réalité le même pari.

### La calibration : ce qui rend le système « intelligent »

Toutes les 24 h, le Chef :

1. Résout les avis arrivés à échéance (l'agent avait-il raison ?)
2. Recalcule le score de Brier de chaque agent, par instrument et par timeframe
3. Met à jour les poids
4. Recalcule les couleurs de la grille de conviction
5. Coupe les couples devenus rouges, réactive ceux redevenus verts
6. Écrit un rapport lisible : *« AG-05 Flux est passé de 0,17 à 0,21 sur le crypto ; AG-06 est tombé sous le seuil sur le forex M15 et est exclu »*

**C'est ça, un système qui réfléchit tout seul.** Pas un agent de plus : une boucle de rétroaction sur les 8 que tu as déjà.

---

## 8. Les 12 skills

Chaque skill va dans `.claude/skills/<nom>/SKILL.md`. Sans elles, Claude Code réinvente une convention différente à chaque session et le projet devient incohérent au bout de 20 fichiers.

### 🔴 Priorité 1 — à écrire en premier

**1. `signal-contract`** — Le schéma JSON unique d'un signal.
```
instrument, marche, tf, sens, entree, sl, tp1, tp2, tp3, rr,
confiance (0-1), volume_calcule, agents_contributeurs [{code, avis, poids}],
raison (texte lisible), invalidation, cree_ts, expire_ts, statut
```
Règle : aucune fonction du système ne manipule un signal dans un autre format. Aucune exception.

**2. `backtest-protocol`** — Le protocole de validation.
- Fenêtres glissantes : 12 mois d'entraînement / 3 mois de test / pas de 1 mois
- Purge de 5 barres entre train et test (pas de fuite de données)
- Coûts **obligatoires** : spread + 1 tick de slippage + commission + funding
- Échantillon minimum : ≥ 30 trades **et** ≥ 2 régimes couverts
- Métriques : R moyen, profit factor, max DD en R, temps de récupération, R du pire creux
- Sortie : verdict AUTORISÉ / REFUSÉ par (instrument × tf × régime)
- **Règle absolue : aucune stratégie n'émet sans avoir passé ce protocole.**

**3. `market-data-adapter`** — Le contrat de chaque source.
Signature identique, normalisation OHLCV, token bucket pour le rate limit, backoff exponentiel, cache DuckDB, tests avec réponses figées. Écrite une fois → les 11 adapters sont cohérents.

**4. `risk-engine`** — Le moteur de risque.
- **Sizing par instrument** : chaque `Instrument` porte sa propre `valeur_point`, son `tick_size`, son `lot_min`. ⚠️ Ça corrige le `VALEUR_POINT_PAR_LOT = 100.0` en dur qui casserait tout hors de l'or.
- Risque ≤ 0,5 % du capital par trade, codé en dur
- Exposition max par marché et globale
- **Matrice de corrélation glissante 90 jours** : deux positions à corr. > 0,7 comptent comme une seule
- Kill switch : −4R sur la journée, ou −8R sur la semaine, ou 5 pertes consécutives → arrêt total jusqu'à validation manuelle

### 🟠 Priorité 2

**5. `agent-loop`** — Comment écrire un agent permanent : boucle asyncio, heartbeat, état persisté, reprise sur crash avec backoff, publication sur le bus, interdiction du blocage. C'est ce qui rend les agents « toujours en ligne ».

**6. `confluence-scoring`** — La pondération par score de Brier, par (instrument × tf), la recalibration 24 h, la détection d'agents corrélés (deux agents qui disent toujours la même chose ne comptent pas double).

**7. `live-testing-grid`** — Le moteur de la grille : comment un couple (instrument × tf) passe de rouge à vert, les seuils exacts, l'échantillon minimum, la fenêtre glissante, le calcul des couleurs. **C'est le cœur de ta capture d'écran.**

**8. `market-regime`** — Classification tendance / range / expansion / compression par actif, et la table : quelle stratégie a le droit de tourner dans quel régime.

**9. `ict-smc-analysis`** — Formalise order blocks, FVG, liquidity sweeps, BOS/CHoCH, premium/discount, sessions Asie/Londres/NY. Rend ton `ict.py` reproductible sur les 4 marchés.

### 🟡 Priorité 3

**10. `news-impact-scoring`** — Transformer une news en score directionnel avec horizon et demi-vie. Fenêtre de blocage automatique : pas d'entrée à T−4 h d'un FOMC / NFP / CPI / earnings.

**11. `notification-router`** — Seuil de confiance, anti-doublon, cooldown par instrument, groupement par marché, format du message ntfy. **Une seule source de vérité pour la pastille de l'interface et la notification téléphone** — sinon les deux divergent et tu ne sais plus lequel croire.

**12. `execution-broker`** — Abstraction d'ordre au-dessus de Binance / MetaApi / Alpaca : idempotence (jamais deux fois le même ordre), réconciliation au démarrage, bascule paper ↔ live, journalisation de chaque ordre envoyé.

### Le `CLAUDE.md` à la racine

```markdown
# Règles du projet — non négociables

1. Aucune stratégie n'émet de signal sans avoir passé `backtest-protocol`.
2. Aucun couple (instrument × tf) n'émet en live si son carreau n'est pas VERT.
3. Tout signal respecte le schéma `signal-contract`. Aucune exception.
4. Aucun accès direct à une API : toujours via un adapter de `feeds/`.
5. La valeur du point vient TOUJOURS de l'objet Instrument. Jamais de constante.
6. Risque par trade ≤ 0,5 % du capital. En dur, non configurable à la volée.
7. Deux positions corrélées à plus de 0,7 comptent comme une seule.
8. Toute nouvelle source arrive avec ses tests et son gestionnaire de rate limit.
9. Aucun fichier ne dépasse 500 lignes. Au-delà : on découpe.
10. Aucune clé API dans le code. `.env` uniquement.
11. `execution/` reste en paper tant qu'un track record de 3 mois n'existe pas.
12. Tout signal émis doit pouvoir expliquer QUI a voté quoi et avec quel poids.
```

---

## 9. Les APIs

**Coût total : 0 €.**

### Crypto — c'est là que le gratuit est le meilleur

| Source | Endpoint | Clé | Limite | Apport |
|---|---|---|---|---|
| **Binance REST** | `/api/v3/klines` | **non** | 1200 poids/min | OHLCV toutes TF, historique complet |
| **Binance WebSocket** | `wss://stream.binance.com:9443` | **non** | illimité | temps réel poussé, zéro polling — c'est ce qui permet la couche « chaque seconde » |
| **Binance Futures** | `/fapi/v1/fundingRate` | non | — | coût du positionnement |
| **Binance Futures** | `/futures/data/openInterestHist` | non | — | argent qui entre / sort |
| **Binance Futures** | `/futures/data/topLongShortPositionRatio` | non | — | ⭐ **positionnement des gros comptes** — l'équivalent crypto du COT, gratuit et **quotidien** au lieu d'hebdomadaire |
| **Bybit v5** | `/v5/market/kline` | non | — | redondance |
| **CoinGecko** | `/api/v3/global` | non | 30/min | dominance BTC |
| **Alternative.me** | `/fng/` | non | — | Fear & Greed |
| **Binance Testnet** | `testnet.binance.vision` | gratuite | — | paper trading avec les vraies mécaniques d'ordre |

Le trio **funding + open interest + ratio long/short** est ce qui manque le plus à ton agent « Minières & Flux ». Sur le crypto c'est gratuit, et ça vaut plus que n'importe quel indicateur technique.

### Forex et matières premières

| Source | Clé | Limite | Usage |
|---|---|---|---|
| **yfinance** | non | quasi illimité | `EURUSD=X`, `GC=F` (or), `SI=F` (argent), `CL=F` (WTI), `DX-Y.NYB` — des années d'historique gratuit |
| **Dukascopy** (`duka`) | non | — | ⭐ **tick data historique de qualité institutionnelle, gratuit** — indispensable pour backtester le forex avec le vrai spread |
| **Twelve Data** (déjà là) | oui | 800/j/clé | temps réel d'appoint, 6-8 paires max |
| **FRED** (déjà là) | gratuite | illimité | taux réels, DXY, inflation, spread 2a/10a |
| **CFTC COT** `publicreporting.cftc.gov/resource/6dca-aqww.json` | non | — | positionnement officiel hebdo — remplace ta valeur COT en dur |
| **MetaApi Cloud** | free tier démo | — | exécution MT5 depuis Mac |

> ⚠️ **Point Mac critique.** Le paquet Python `MetaTrader5` est **Windows uniquement**. Depuis macOS tu ne peux pas piloter MT5 en direct. Deux voies : **MetaApi Cloud** (pont cloud vers ton compte MT5, free tier sur démo) ou une VM Windows — tu as déjà Parallels et VirtualBox installés. MetaApi est plus propre pour du 24/7.

### Actions

| Source | Clé | Limite | Usage |
|---|---|---|---|
| **yfinance** | non | — | OHLCV, fondamentaux, dates d'earnings |
| **Alpaca** | gratuite | illimitée en paper | données IEX temps réel + **paper trading avec vraie API d'ordre** |
| **Finnhub** | gratuite | 60/min | news par ticker, calendrier earnings, recommandations |
| **FMP** | gratuite | 250/j | ratios fondamentaux |
| **SEC EDGAR full-text** | **non** | — | dépôts 8-K / 10-Q en quasi temps réel |
| **FINRA** | non | — | intérêt vendeur, bimensuel |

### News, macro, sentiment — transversal

| Source | Clé | Pourquoi |
|---|---|---|
| **GDELT 2.0 DOC API** | **non** | ⭐ Indexe la presse mondiale **toutes les 15 minutes** avec un score de tonalité, requêtable par entité et par pays. Saut qualitatif énorme par rapport à 5 flux RSS — gratuit, sans inscription. |
| **Finnhub news** | gratuite | news attachée au ticker |
| **Marketaux** | gratuite | 100/j, sentiment pré-scoré |
| **ForexFactory** (déjà là) | non | calendrier économique |
| **Reddit API** | gratuite | sentiment retail crypto / actions |

### Ordre de création des clés

1. **Aucune clé requise** → Binance, Bybit, GDELT, CFTC, SEC, yfinance, Dukascopy, CoinGecko, Alternative.me → **tu peux démarrer aujourd'hui**
2. `alpaca.markets` → clé paper (2 min, gratuit à vie)
3. `finnhub.io` → clé gratuite
4. `metaapi.cloud` → compte + connexion du compte démo MT5
5. Binance → clé testnet

---

## 10. Le plan par phases

| Phase | Contenu | Durée | Critère de sortie |
|---|---|---|---|
| **0** | `CLAUDE.md`, skills 1-4, `core/contracts.py`, `feeds/base.py`, DuckDB. Rendre `features/` symbole-agnostique. **Corriger `VALEUR_POINT_PAR_LOT`.** | 2-3 j | Tests verts, comportement identique sur XAU/USD |
| **1** | `research/walkforward.py` + `research/livetest.py`. Rejouer la stratégie sur 20 instruments × 4 TF avec coûts réels. | 4-5 j | ⭐ **Tu sais quelles combinaisons ont un edge.** La grille a ses premières couleurs. |
| **2** | Adapters Binance (REST+WS), Bybit, yfinance, CoinGecko. Univers crypto + matières premières. | 3-4 j | 42 instruments alimentés en continu |
| **3** | `core/bus.py`, `agents/base.py`, migration des 8 agents en boucles permanentes, `agents/correlation.py`. | 4-5 j | Le système tourne 24 h sans intervention, heartbeats verts |
| **4** | `agents/chef.py` — fusion Probabilité + Opportunité + Superviseur, pondération par Brier, recalibration 24 h. | 4 j | Les poids bougent tout seuls et le rapport quotidien est lisible |
| **5** | `decision/risk.py` + `decision/router.py` + journal unifié. | 3 j | Aucun signal n'échappe au filtre risque |
| **6** | FastAPI + SSE + l'interface : 4 tuiles → grille de conviction → fiche multi-TF. | 5-6 j | ⭐ Ton écran cible fonctionne |
| **7** | Adapters forex (Dukascopy, MetaApi) + actions (Alpaca, Finnhub, SEC). | 4 j | 100 instruments |
| **8** | `execution/paper.py` + Binance testnet + Alpaca paper. **Minimum 3 mois.** | 3 mois | PF > 1,3 et max DD < 15 % sur ≥ 100 trades |
| **9** | Live sur petit capital, **un seul marché**, taille réduite. | — | uniquement si la phase 8 est concluante |

---

## 11. Les prompts

### Phase 0

```
Lis tout gold_agent/. Objectif : rendre le système multi-actifs sans changer
son comportement sur XAU/USD.

1. Crée CLAUDE.md à la racine avec les 12 règles non négociables (je te les fournis).
2. Crée .claude/skills/ avec signal-contract, backtest-protocol,
   market-data-adapter et risk-engine.
3. Crée core/contracts.py :
   - Instrument(symbole, marche, classe, source, tick_size, valeur_point,
     lot_min, lot_pas, session, frais_bps)
   - Bar(time, open, high, low, close, volume)
   - Signal(schéma complet du skill signal-contract)
   - AgentMessage(code_agent, instrument, tf, direction, force, horizon,
     raison, ts)
4. BUG CRITIQUE à corriger : VALEUR_POINT_PAR_LOT = 100.0 est en dur dans
   risk.py ET dans notify.py. Sur BTC ou EURUSD le sizing serait faux d'un
   facteur 100 à 100 000. Cette valeur doit venir de l'objet Instrument.
5. Retire toute occurrence en dur de "XAU/USD" : chaque fonction de features/
   prend un Instrument en paramètre.
6. Remplace config.TF_EMISSION_DEFAUT (liste globale) par une table
   {(instrument, tf): verdict} persistée.
7. Écris les tests qui prouvent que la sortie sur XAU/USD est identique
   à avant le refactor.

Ne touche à rien d'autre. Aucune nouvelle source de données dans cette étape.
```

### Phase 1 — la plus importante

```
Crée research/walkforward.py et research/livetest.py.

walkforward.py, protocole imposé :
- fenêtres glissantes 12 mois train / 3 mois test / pas de 1 mois
- purge de 5 barres entre train et test
- coûts appliqués : spread + 1 tick de slippage + commission + funding (crypto)
- échantillon minimum : 30 trades ET au moins 2 régimes couverts
- métriques : R moyen, profit factor, max DD en R, temps de récupération,
  R du pire creux, taux de réussite, durée moyenne
- sortie : tableau (instrument × tf × régime) → verdict AUTORISÉ / REFUSÉ

livetest.py : le moteur de la grille de conviction.
- maintient pour chaque couple (instrument × tf) un état roulant sur
  90 jours glissants : R cumulé, nb trades, win rate, PF, durée moyenne
- couleurs : VERT (R>+0.3 ET PF>1.3 ET >=30 trades) / BLEU (edge positif,
  échantillon court) / GRIS (neutre) / ROUGE (R<0)
- seuls les VERTS ont le droit d'émettre en live
- expose get_grille(marche) -> list[CarreauInstrument] pour l'interface

Puis fais tourner walkforward sur : XAUUSD, XAGUSD, BTCUSDT, ETHUSDT,
SOLUSDT, EURUSD, GBPUSD, USDJPY, SPY, QQQ — en H1, M30, M15, M5.
Écris le résultat dans research/rapport_edge.md.
```

### Phase 2

```
Crée feeds/base.py : classe abstraite Feed avec fetch_ohlcv(instrument, tf,
depuis, jusqu_a), stream(instruments, callback), token bucket pour le rate
limit, backoff exponentiel, cache DuckDB, tests avec réponses figées.

Puis :
- feeds/binance.py : REST /api/v3/klines + WebSocket kline streams +
  /fapi/v1/fundingRate + /futures/data/openInterestHist +
  /futures/data/topLongShortPositionRatio
- feeds/bybit.py : /v5/market/kline (redondance)
- feeds/yahoo.py : via yfinance, pour GC=F SI=F CL=F EURUSD=X DX-Y.NYB
  et les actions

Aucune clé API pour Binance, Bybit et yfinance.
Chaque adapter a ses tests avant d'être considéré comme fini.
```

### Phase 4 — le Chef d'orchestre

```
Crée agents/chef.py qui fusionne AG-06 Probabilité, AG-07 Opportunités et
AG-00 Superviseur en un seul Chef d'orchestre.

Responsabilités :
1. Collecter les AgentMessage de tous les agents par (instrument × tf)
2. Pondérer chaque agent par son score de Brier sur ses 100 derniers avis
   RÉSOLUS, calculé séparément pour chaque couple (instrument, tf).
   Les poids sont CALCULÉS, jamais choisis à la main.
3. Émettre seulement si les 5 conditions sont réunies :
   carreau VERT + confluence >= 0.65 + >= 3 agents indépendants d'accord
   + R:R >= 1.5 après coûts + filtre risque passé
4. Superviser : heartbeats, taux d'erreur, dérive. Exclure du vote tout
   agent mort ou dont le score passe sous le seuil.
5. Arbitrer entre instruments : max 3 signaux simultanés, non corrélés
   entre eux (corr < 0.7).
6. Recalibration toutes les 24 h : résoudre les avis échus, recalculer les
   scores de Brier, mettre à jour les poids et les couleurs de la grille,
   écrire un rapport lisible dans agents/rapport_calibration.md.

Deux agents dont les avis sont corrélés à plus de 0.8 ne comptent pas double :
détecte-les et fusionne leur poids.
```

### Phase 6 — l'interface

```
Crée api/ (FastAPI + SSE) et ui/.

Endpoints :
  GET /api/markets                          → 4 tuiles : nb actifs, R total,
                                               nb verts, nb signaux actifs
  GET /api/markets/{marche}/grille          → les carreaux, triés par R desc
  GET /api/instruments/{symbole}             → fiche : 4 colonnes H1/M30/M15/M5
  GET /api/instruments/{symbole}/pourquoi    → le détail du vote des agents
  GET /api/stream                            → SSE : push des nouveaux signaux
                                               et des changements de prix

Carreau (le JSON exact) :
{ symbole, marche, r_cumule, variation_pct_24h, nb_trades, win_rate,
  profit_factor, duree_moyenne_h, couleur, signaux_actifs }

Interface : 3 niveaux — 4 tuiles marché → grille de carreaux (dégradé vert
vif → vert → bleu → gris → rouge, comme une heatmap) → fiche instrument avec
les 4 timeframes côte à côte et le bloc POURQUOI.

Filtres sur la grille : Tous / Verts seulement / Signal actif ; tri par
R, PF, variation, nb de trades.

HTML + Alpine.js, pas de React. Remplace intégralement web.py.
```

---

## 12. Les pièges

**1. Le sizing multi-marchés.** `VALEUR_POINT_PAR_LOT = 100.0` est correct pour XAUUSD et faux pour tout le reste. Un lot EURUSD vaut 10 $/pip, un contrat BTC vaut 1 BTC. Si cette constante survit au refactor, le premier trade crypto passera en taille × 1000. **C'est le bug qui vide un compte en une nuit, et personne ne regarde à 4 h du matin.**

**2. La corrélation déguisée.** Long or + long argent + short DXY + long BTC, ce n'est pas 4 positions à 0,5 % de risque. C'est **une seule position à 2 %**. C'est le piège n°1 du multi-marchés et c'est précisément ce que tu es en train de construire. `agents/correlation.py` doit exister avant le premier trade multi-marchés, pas après.

**3. Le backtest sans coûts.** Sur du M5, spread + slippage transforment couramment un +0,4R affiché en −0,1R réel. C'est la première cause de systèmes qui « marchent en backtest » et perdent en réel. Ton M15 à +0,06R est probablement déjà négatif une fois les coûts comptés — tu as eu raison de le couper.

**4. Le surapprentissage sur 100 actifs.** Si tu testes 100 instruments × 4 TF × 10 jeux de paramètres = 4 000 combinaisons, **une centaine paraîtra excellente par pur hasard**. C'est exactement pour ça que le walk-forward avec fenêtres glissantes est obligatoire : une combinaison qui gagne sur 8 fenêtres consécutives n'est pas un hasard. Une qui gagne « en moyenne sur 3 ans », si.

**5. Le sur-signal.** Un système qui émet 4 signaux/jour à 40 % de réussite perd. Le même qui émet 4 signaux/semaine en ne gardant que les confluences fortes gagne. **Le taux d'émission est ton levier le plus puissant, et il se règle à la baisse.**

**6. L'illusion du « chaque seconde ».** Recalculer la structure H1 chaque seconde produit 3 600 fois le même résultat et pousse à réagir au bruit intra-bougie. La bonne architecture est celle du §6 : prix en temps réel, déclencheurs à la seconde, analyse à la clôture de bougie.

---

## Ce que je te recommande de faire maintenant

Dans cet ordre, et pas un autre :

1. **Phase 0** — le refactor et surtout la correction de `VALEUR_POINT_PAR_LOT`. Rien ne doit avancer avant.
2. **Phase 1** — le walk-forward. C'est ce qui donne ses premières couleurs à ta grille, et c'est ce qui te dira si ta stratégie a un edge **avant** que tu construises 6 semaines d'infrastructure autour.
3. **Phase 2** — Binance, gratuit et sans clé, 30 instruments crypto d'un coup.

Si la phase 1 montre que l'edge est là, tout le reste vaut la peine d'être construit. Si elle montre qu'il n'y est pas, tu l'auras appris en 5 jours au lieu de 3 mois — et tu sauras exactement quoi corriger dans la stratégie.

---

## Sources

- [Best Free Stock Market APIs and Data Tools in 2026 — DEV Community](https://dev.to/nexgendata/best-free-stock-market-apis-and-data-tools-in-2026-a-developers-honest-comparison-1926)
- [The 7 Best Real-Time Stock Data APIs 2026 — Coinmonks](https://medium.com/coinmonks/the-7-best-real-time-stock-data-apis-for-investors-and-developers-in-2026-in-depth-analysis-61614dc9bf6c)
- [Python integration on Mac OS — forum MQL5](https://www.mql5.com/en/forum/478849)
- [MetaApi — Cloud forex trading API for MetaTrader](https://metaapi.cloud/docs/client/)
- [Best MetaApi Alternatives for MT4/MT5 — API2Trade](https://www.api2trade.com/blog/best-metaapi-alternatives-mt4-mt5/)
