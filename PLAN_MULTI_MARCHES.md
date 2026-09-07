# Plan d'évolution — de `gold_agent` à un système multi-marchés autonome

*Établi le 7 septembre 2026, après lecture du code dans `~/Trading Claude/gold_agent`.*

---

## 0. Ce que j'ai vu dans ton code

Ce que tu as construit est sérieux. Concrètement :

- `datasource.py` — Twelve Data avec **rotation automatique de clés** et TTL adaptatif. C'est une vraie ingénierie de contournement de quota.
- `config.py` — l'émission est limitée à H4/H1/M30 **parce que le backtest le dit** (M15 à +0,06R et M5 à 17 jours de données sont coupés). C'est la meilleure décision de tout le projet.
- `strategy.py`, `ict.py`, `patterns.py`, `regime.py`, `structure.py`, `indicators.py` — la couche analyse est déjà riche.
- `debate.py` — consensus pondéré entre agents.
- `journal.py` + `backtest.py` + `risk.py` + `notify.py` (ntfy) — la boucle de mesure existe.

**Les 4 blocages structurels pour passer au multi-marchés :**

| Blocage | Détail | Conséquence |
|---|---|---|
| **XAU/USD est câblé en dur** | `symbole="XAU/USD"` par défaut partout, `TF_EMISSION_DEFAUT` global | Impossible d'avoir un réglage par actif |
| **`web.py` fait 87 Ko** | HTTP serveur + HTML + logique métier dans un seul fichier | Chaque ajout devient plus coûteux ; Claude Code va s'y perdre |
| **Twelve Data ne scalera jamais** | 800 requêtes/jour/clé. 60 actifs × 5 TF × rafraîchissement 5 min = **86 400 requêtes/jour** | Il faut changer de source, pas ajouter des clés |
| **Les agents ne sont pas permanents** | Ce sont des fonctions appelées au rendu de page, pas des processus | « Toujours en ligne, réfléchit toujours » n'existe pas encore |

---

## 1. La chose la plus importante à te dire

Tu as écrit dans ta demande : *« une marge de perte égale à zéro… je sais que c'est pas possible, mais je veux diminuer la perte au maximum ».*

Ta capture d'écran affiche **`journal réel : 0.0%` et `1 setup(s)`**. Autrement dit : le système ne dispose pas encore de la preuve qu'il gagne sur **un seul** marché.

Le réflexe naturel est d'ajouter du forex, du crypto et des actions pour multiplier les occasions. En réalité, ajouter 3 marchés à un système non prouvé **multiplie les pertes par 4, pas les gains**. Un système qui perd 0,3R par trade sur l'or perdra 0,3R par trade sur le Bitcoin, plus vite, parce que le crypto tourne 24/7.

**La bonne séquence :**

1. D'abord l'infrastructure de **mesure** (protocole de backtest walk-forward + journal live). C'est le seul truc qui transforme une intuition en edge.
2. Ensuite le refactor multi-actifs — pour que *le même moteur prouvé* tourne sur 60 instruments.
3. Ensuite seulement l'exécution automatique, et en paper d'abord.

La réduction de perte ne vient pas d'agents supplémentaires. Elle vient de trois leviers, dans cet ordre :

- **Le taux d'émission.** Un système qui émet 4 signaux/jour avec 40 % de réussite perd. Le même qui émet 4 signaux/semaine en ne gardant que les confluences fortes gagne. Ton filtre `TF_EMISSION_DEFAUT` fait déjà ça — il faut le généraliser à *chaque paire (actif × timeframe × régime)*.
- **Le risque par trade.** 0,25 à 0,5 % du capital. À 0,5 %, il faut 20 pertes consécutives pour perdre 10 %. À 2 %, il en faut 5.
- **La corrélation.** Long or + long argent + short DXY + long BTC = **une seule position** déguisée en quatre. C'est le piège n°1 du multi-marchés, et c'est précisément ce que tu t'apprêtes à construire. Il faut un moteur de corrélation avant le premier trade multi-marchés.

---

## 2. Architecture cible

```
trading_system/
├── core/
│   ├── contracts.py       # Bar, Signal, Instrument, AgentMessage — schémas uniques
│   ├── bus.py             # bus asyncio (upgradeable Redis) : publish/subscribe
│   └── store.py           # DuckDB : barres, signaux, trades, métriques agents
├── feeds/                 # 1 fichier par source, TOUS le même contrat
│   ├── base.py            # classe Feed : fetch_ohlcv, stream, rate limit, backoff, cache
│   ├── binance.py         # crypto — REST + WebSocket
│   ├── bybit.py           # crypto — redondance
│   ├── yahoo.py           # forex, matières premières, actions (historique)
│   ├── twelvedata.py      # existant, rétrogradé en source d'appoint
│   ├── dukascopy.py       # tick data forex historique (backtest)
│   ├── alpaca.py          # actions temps réel + exécution paper
│   ├── fred.py            # macro (existant)
│   ├── cot.py             # positionnement CFTC
│   ├── gdelt.py           # news mondiale + tonalité
│   └── finnhub.py         # news par ticker, earnings
├── features/              # ← ton code actuel, rendu symbole-agnostique
│   ├── indicators.py  structure.py  ict.py  patterns.py  regime.py
├── agents/                # processus permanents, une boucle chacun
│   ├── base.py            # Agent : run(), heartbeat, état, reprise sur crash
│   ├── vigie.py  structure_agent.py  strategie.py  traceur.py
│   ├── flux.py            # COT + funding + open interest + ratio long/short
│   ├── probabilite.py  opportunites.py  superviseur.py
│   └── correlation.py     # ← NOUVEAU, indispensable en multi-marchés
├── decision/
│   ├── confluence.py      # fusion pondérée par performance mesurée
│   ├── risk.py            # sizing, exposition, kill switch
│   └── router.py          # règles de notification
├── execution/
│   ├── base.py            # interface Broker : place, modify, cancel, positions
│   ├── binance_ex.py  metaapi_ex.py  alpaca_ex.py  paper.py
├── research/
│   ├── walkforward.py     # LE module qui décide ce qui a le droit d'émettre
│   └── metrics.py
├── api/                   # FastAPI + SSE (remplace web.py)
└── ui/                    # 4 tuiles marché → grille actifs → fiche setup
```

**Le principe qui tient tout :** un `Signal` a exactement le même schéma qu'il vienne du Bitcoin, de l'EUR/USD ou de Nvidia. Toute la logique en aval (risque, notification, journal, backtest) devient marché-agnostique et tu écris chaque brique **une seule fois**.

### Univers d'actifs — ne pas viser 5 000 tickers

| Marché | Instruments | Pourquoi ceux-là |
|---|---|---|
| Matières premières | XAU/USD, XAG/USD, WTI, Brent, cuivre, gaz naturel | ton terrain actuel + ce qui corrèle avec |
| Forex | 7 majeures + 6 crosses (EURJPY, GBPJPY, AUDNZD…) + DXY | liquidité, spreads serrés |
| Crypto | BTC, ETH, SOL, BNB, XRP + 10 alts à forte capitalisation | 24/7, données gratuites parfaites |
| Actions | ~25 : les 7 mégacaps + 3 ETF sectoriels + SPY/QQQ | earnings et news exploitables |

**~60 instruments.** Au-delà, le bruit augmente plus vite que le signal, et tu ne peux plus auditer ce que le système fait.

---

## 3. Les APIs — toutes gratuites

### 3.1 Crypto — c'est là que le gratuit est le meilleur

| Source | Endpoint | Clé | Limite | Ce que ça t'apporte |
|---|---|---|---|---|
| **Binance REST** | `api.binance.com/api/v3/klines` | **non** | 1200 poids/min | OHLCV toutes TF, historique complet |
| **Binance WebSocket** | `wss://stream.binance.com:9443` | **non** | illimité | temps réel vrai, zéro polling |
| **Binance Futures** | `/fapi/v1/fundingRate` | non | — | funding rate = coût du positionnement long/short |
| **Binance Futures** | `/futures/data/openInterestHist` | non | — | open interest = argent qui entre/sort |
| **Binance Futures** | `/futures/data/topLongShortPositionRatio` | non | — | **positionnement des gros comptes** — c'est l'équivalent crypto du COT, et c'est gratuit et quotidien au lieu d'hebdomadaire |
| **Bybit v5** | `api.bybit.com/v5/market/kline` | non | — | redondance si Binance tombe |
| **CoinGecko** | `/api/v3/global` | non | 30 req/min | dominance BTC, cap totale |
| **Alternative.me** | `api.alternative.me/fng/` | non | — | Fear & Greed index |
| **Binance Testnet** | `testnet.binance.vision` | oui (gratuite) | — | **paper trading avec les vraies mécaniques d'ordre** |

→ Le trio **funding + open interest + ratio long/short** est ce qui manque le plus à ton agent « Minières & Flux » actuel. Sur le crypto c'est gratuit et ça vaut plus que n'importe quel indicateur technique.

### 3.2 Forex et matières premières

| Source | Clé | Limite | Usage |
|---|---|---|---|
| **yfinance** (`pip install yfinance`) | non | pratiquement illimité | `EURUSD=X`, `GC=F` (or), `SI=F` (argent), `CL=F` (WTI), `DX-Y.NYB` — **des années d'historique gratuit** |
| **Dukascopy** (`duka` / `dukascopy-node`) | non | — | **tick data historique de qualité institutionnelle, gratuit** — indispensable pour backtester le forex avec le vrai spread |
| **Twelve Data** (déjà en place) | oui | 800/jour/clé | temps réel d'appoint sur 6-8 paires max |
| **FRED** (déjà en place) | oui, gratuite | illimité | taux, inflation, spread 2 ans/10 ans, DXY |
| **CFTC COT** — `publicreporting.cftc.gov/resource/6dca-aqww.json` | non | — | positionnement officiel hebdo : or, argent, devises, indices. **Remplace ta valeur COT en dur.** |
| **MetaApi Cloud** | oui | free tier démo | **exécution MT5 depuis un Mac** — voir l'avertissement ci-dessous |

> ⚠️ **Important — tu es sur Mac.** Le paquet Python `MetaTrader5` est **Windows uniquement**. Depuis macOS, tu ne peux pas piloter MT5 en direct. Les deux voies réelles : **MetaApi Cloud** (un pont cloud vers ton compte MT5, free tier sur compte démo) ou une VM Windows (tu as déjà Parallels et VirtualBox installés). MetaApi est plus propre pour un système qui doit tourner 24/7.

### 3.3 Actions

| Source | Clé | Limite | Usage |
|---|---|---|---|
| **yfinance** | non | — | OHLCV, fondamentaux, dates d'earnings |
| **Alpaca** | oui, gratuite | illimitée en paper | données IEX temps réel **+ paper trading avec vraie API d'ordre** |
| **Finnhub** | oui, gratuite | 60 req/min | news par ticker, calendrier earnings, recommandations analystes |
| **FMP** | oui, gratuite | 250 req/jour | ratios fondamentaux |
| **SEC EDGAR full-text** | non | — | dépôts 8-K / 10-Q en quasi temps réel, gratuit et sans clé |
| **FINRA short interest** | non | — | intérêt vendeur, bimensuel |

### 3.4 News, macro, sentiment — transversal

| Source | Clé | Pourquoi |
|---|---|---|
| **GDELT 2.0 DOC API** | **non** | Indexe la presse mondiale **toutes les 15 minutes** avec un score de tonalité, requêtable par entité et par pays. C'est un saut qualitatif énorme par rapport à tes 5 flux RSS actuels — et c'est gratuit sans inscription. |
| **Finnhub news** | gratuite | news attachée au ticker |
| **Marketaux** | gratuite | 100 req/jour, sentiment pré-scoré |
| **ForexFactory** (déjà) | non | calendrier économique |
| **FRED** (déjà) | gratuite | macro US |
| **Reddit API** | gratuite | sentiment retail crypto/actions |

### 3.5 À créer maintenant, dans cet ordre

1. **Aucune clé** : Binance, Bybit, GDELT, CFTC, SEC, yfinance, Dukascopy, CoinGecko, Alternative.me → tu peux commencer **aujourd'hui**
2. `alpaca.markets` → clé paper (2 min, gratuit à vie)
3. `finnhub.io` → clé gratuite
4. `metaapi.cloud` → compte + connexion de ton compte démo MT5
5. Binance → clé testnet

Coût total : **0 €**.

---

## 4. Les skills Claude Code à écrire

C'est ce qui va faire la différence. Sans skills, Claude Code réinvente une convention différente à chaque session et ton projet devient incohérent au bout de 20 fichiers. Chaque skill va dans `.claude/skills/<nom>/SKILL.md`.

| # | Skill | Rôle | Priorité |
|---|---|---|---|
| 1 | **`signal-contract`** | Le schéma JSON unique d'un signal (symbole, marché, TF, sens, entrée, SL, TP1/2/3, R:R, confiance, agents contributeurs, condition d'invalidation, expiration). Tout le système parle ce format. | 🔴 en premier |
| 2 | **`backtest-protocol`** | Walk-forward avec fenêtres glissantes, purge, coûts réels (spread + slippage + funding + commission), échantillon minimum (≥ 30 trades, ≥ 2 régimes), métriques obligatoires (R moyen, profit factor, max DD en R, temps de récupération). **Règle : aucune stratégie n'a le droit d'émettre sans avoir passé ce protocole.** | 🔴 en premier |
| 3 | **`market-data-adapter`** | Le contrat que respecte chaque source : signature, normalisation OHLCV, gestion du rate limit, backoff exponentiel, cache, tests avec réponses figées. Écrite une fois → les 11 adapters sont cohérents. | 🔴 en premier |
| 4 | **`risk-engine`** | Sizing par ATR, risque max/trade + /marché + global, matrice de corrélation, exposition nette par devise, kill switch après N pertes ou X% de drawdown. | 🔴 |
| 5 | **`agent-loop`** | Comment écrire un agent permanent : boucle asyncio, intervalle, heartbeat, état persisté, reprise après crash, publication sur le bus, jamais d'appel bloquant. C'est ce qui rend tes agents « toujours en ligne ». | 🟠 |
| 6 | **`confluence-scoring`** | Fusion des avis d'agents avec des poids **issus de leur performance mesurée**, jamais de poids arbitraires. Ton `debate.py` généralisé et auto-calibré. | 🟠 |
| 7 | **`market-regime`** | Classification tendance / range / expansion / compression, par actif. Et la table : quelle stratégie a le droit de tourner dans quel régime. | 🟠 |
| 8 | **`ict-smc-analysis`** | Formalise order blocks, FVG, liquidity sweeps, BOS/CHoCH, premium/discount, sessions. Rend ton `ict.py` reproductible sur les 4 marchés. | 🟠 |
| 9 | **`news-impact-scoring`** | Transformer une news en score directionnel avec horizon et demi-vie ; bloquer les entrées dans la fenêtre des événements à fort impact (NFP, FOMC, CPI, earnings). | 🟡 |
| 10 | **`notification-router`** | Règles de déclenchement d'une notification : seuil de confiance, anti-doublon, cooldown, groupement par marché. **C'est ce qui alimente les pastilles de ton interface.** | 🟡 |
| 11 | **`execution-broker`** | Abstraction d'ordre au-dessus de Binance / MetaApi / Alpaca : idempotence, réconciliation, mode paper ↔ live, journalisation de chaque ordre. | 🟡 |

Il te faut aussi un **`CLAUDE.md`** à la racine avec les règles non négociables du projet — c'est lu à chaque session :

```markdown
# Règles du projet — non négociables

1. Aucune stratégie n'émet de signal sans avoir passé `backtest-protocol`.
2. Tout signal respecte le schéma `signal-contract`. Aucune exception.
3. Aucun accès direct à une API : toujours via un adapter de `feeds/`.
4. Risque par trade ≤ 0,5 % du capital. Codé en dur, pas configurable à la volée.
5. Toute nouvelle source de données arrive avec ses tests et son gestionnaire de rate limit.
6. Aucun fichier ne dépasse 500 lignes. Au-delà : on découpe.
7. Aucune clé API dans le code. `.env` uniquement.
8. `execution/` fonctionne en paper tant qu'un track record de 3 mois n'existe pas.
```

---

## 5. L'interface que tu décris

Ton idée (4 tuiles marché → grille d'actifs → pastille de notification → fiche setup) est la bonne. Techniquement :

```
GET /api/markets                          → 4 tuiles + nb d'opportunités actives
GET /api/markets/crypto/instruments       → grille : BTC, ETH, SOL… + badge par actif
GET /api/instruments/BTCUSDT/signal       → entrée / SL / TP / R:R / raisons / agents
GET /api/stream                           → SSE : push temps réel des nouvelles opportunités
```

Le badge sur une case = le nombre de signaux actifs sur cet actif dont la confiance dépasse le seuil défini dans `notification-router`. Le même calcul alimente la notification ntfy sur ton téléphone. **Une seule source de vérité pour les deux** — sinon l'interface et le téléphone divergent et tu ne sais plus lequel croire.

FastAPI + SSE remplace ton `web.py`. Front : HTML + Alpine.js suffit largement, pas besoin de React.

---

## 6. Le plan par phases

| Phase | Contenu | Durée | Critère de sortie |
|---|---|---|---|
| **0** | `core/contracts.py`, `feeds/base.py`, DuckDB, `.claude/skills/` (skills 1-3), `CLAUDE.md`. Rendre `features/` symbole-agnostique. | 2-3 j | Les tests passent, le comportement sur XAU/USD est identique à aujourd'hui |
| **1** | `research/walkforward.py`. Rejouer ta stratégie sur XAU/USD + 5 crypto avec coûts réels. | 3-4 j | **Tu sais quelles combinaisons (actif × TF) ont un edge positif.** Les autres sont coupées. |
| **2** | Adapters Binance (REST + WS), Bybit, yfinance, CoinGecko. Univers crypto + matières premières. | 3-4 j | 25 instruments alimentés en continu |
| **3** | `core/bus.py`, `agents/base.py`, migration des 8 agents en boucles permanentes + `agents/correlation.py`. | 4-5 j | Le système tourne 24 h sans intervention, heartbeats verts |
| **4** | `decision/risk.py`, `decision/router.py`, journal unifié. | 3 j | Aucun signal n'échappe au filtre risque |
| **5** | FastAPI + SSE + l'interface 4 tuiles. | 4-5 j | Ton écran cible fonctionne |
| **6** | Adapters forex (Dukascopy, MetaApi) + actions (Alpaca, Finnhub, SEC). | 4 j | 60 instruments |
| **7** | `execution/paper.py` + Binance testnet + Alpaca paper. **Minimum 3 mois.** | 3 mois | Profit factor > 1,3 et max DD < 15 % sur ≥ 100 trades |
| **8** | Live sur petit capital, un seul marché, taille réduite. | — | seulement si la phase 7 est concluante |

---

## 7. Prompts prêts à coller dans Claude Code

**Phase 0 :**

```
Lis tout gold_agent/. Objectif : le rendre multi-actifs sans changer son
comportement actuel sur XAU/USD.

1. Crée core/contracts.py avec des dataclasses Instrument (symbole, marché,
   classe, tick_size, session, source), Bar, Signal (schéma complet :
   symbole, marché, tf, sens, entree, sl, tp1/2/3, rr, confiance 0-1,
   agents_contributeurs, raison, invalidation, expire_a) et AgentMessage.
2. Retire toute occurrence en dur de "XAU/USD" : chaque fonction de
   features/ prend un Instrument en paramètre.
3. Remplace config.TF_EMISSION_DEFAUT (liste globale) par une table
   {instrument: [timeframes autorisés]} persistée en JSON.
4. Écris les tests qui prouvent que la sortie sur XAU/USD est identique
   à avant le refactor.

Ne touche à rien d'autre. Pas de nouvelle source de données dans cette étape.
```

**Phase 1 (la plus importante) :**

```
Crée research/walkforward.py.

Protocole imposé :
- fenêtres glissantes : 12 mois d'entraînement, 3 mois de test, pas de 1 mois
- purge de 5 barres entre train et test (pas de fuite de données)
- coûts appliqués : spread + 1 tick de slippage + commission + funding (crypto)
- échantillon minimum : 30 trades ET couverture d'au moins 2 régimes
- métriques retournées : R moyen, profit factor, max drawdown en R,
  temps de récupération, R du pire creux, taux de réussite
- sortie : un tableau (instrument × timeframe × régime) avec un verdict
  AUTORISÉ / REFUSÉ

Puis fais tourner ce protocole sur XAU/USD, BTCUSDT, ETHUSDT, EURUSD, SPY.
Écris le résultat dans research/rapport_edge.md.
Aucune combinaison REFUSÉE ne doit pouvoir émettre de signal.
```

**Phase 2 :**

```
Crée feeds/base.py (classe abstraite Feed : fetch_ohlcv, stream, rate limit
avec token bucket, backoff exponentiel, cache DuckDB, tests avec réponses figées),
puis feeds/binance.py (REST /api/v3/klines + WebSocket kline streams + funding
rate + open interest + top long/short ratio), feeds/bybit.py, feeds/yahoo.py
(via yfinance, pour GC=F SI=F CL=F EURUSD=X DX-Y.NYB et les actions).

Aucune clé API n'est requise pour Binance, Bybit et yfinance.
Chaque adapter doit avoir ses tests avant d'être considéré comme fini.
```

---

## 8. Ce que je te recommande de ne PAS faire

- **N'ajoute pas d'agents.** Tu en as 8. Le problème n'est pas leur nombre, c'est qu'aucun n'a de poids issu d'une performance mesurée. Un 9ᵉ agent n'améliore rien ; la calibration des 8 existants, si.
- **Ne passe pas en live avant la phase 7.** Un bug de sizing sur un système multi-marchés qui tourne 24/7 vide un compte en une nuit, et personne ne regarde à 4 h du matin.
- **Ne branche pas 200 actifs.** Tu ne pourras plus auditer ce que le système fait, et le jour où il perd tu ne sauras pas pourquoi.
- **Ne fais pas confiance à un backtest sans coûts.** Sur du M15, spread + slippage transforment couramment un +0,4R affiché en −0,1R réel. C'est la première cause de systèmes qui « marchent en backtest » et perdent en réel.

---

## Sources

- [Best Free Stock Market APIs and Data Tools in 2026 — DEV Community](https://dev.to/nexgendata/best-free-stock-market-apis-and-data-tools-in-2026-a-developers-honest-comparison-1926)
- [The 7 Best Real-Time Stock Data APIs 2026 — Coinmonks](https://medium.com/coinmonks/the-7-best-real-time-stock-data-apis-for-investors-and-developers-in-2026-in-depth-analysis-61614dc9bf6c)
- [Python integration on Mac OS — forum MQL5](https://www.mql5.com/en/forum/478849)
- [MetaApi — Cloud forex trading API for MetaTrader](https://metaapi.cloud/docs/client/)
- [Best MetaApi Alternatives for MT4/MT5 — API2Trade](https://www.api2trade.com/blog/best-metaapi-alternatives-mt4-mt5/)
