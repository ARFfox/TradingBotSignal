# Agent d'analyse — Or (XAU/USD)

Agent d'analyse technique multi-timeframe sur l'or, branché sur TradingView
Desktop via le Chrome DevTools Protocol.

**Analyse uniquement.** L'agent ne passe aucun ordre et ne fournit pas de
conseil en investissement.

## Architecture

```
TradingView Desktop (CDP :9222)
        │
        ▼
claudeverstradingview  (~/claudeverstradingview)   ← pont MCP/CLI
        │  symbol, timeframe, ohlcv, quote
        ▼
gold_agent/            (ce dossier)                ← moteur d'analyse
        ├── bridge.py       appels CLI + relance auto de TradingView
        ├── indicators.py   EMA, RSI, ATR, MACD, ADX, Bollinger (Python pur)
        ├── structure.py    pivots, tendance HH/HL, supports/résistances
        ├── analyze.py      moteur multi-timeframe 1D → H4 → H1
        ├── debate.py       débat contradictoire + garde-fou de risque
        ├── patterns.py     zigzag, Elliott, order blocks, sessions
        ├── regime.py       volatilité, renversement, score d'extension gradué
        ├── notify.py       notifications système + push téléphone
        ├── tableau.py      collecte des données du tableau de bord
        ├── web.py          serveur + interface du tableau de bord
        ├── draw_levels.py  tracé des zones sur TradingView
        ├── risk.py         calculateur de position (tes niveaux, son arithmétique)
        ├── calc.py         point d'entrée du calculateur
        ├── strategy.py     règle mécanique + simulation sans lookahead
        ├── backtest.py     point d'entrée du backtest
        ├── setup.py        zones entrée/stop/objectif de la règle
        └── datasource.py   Twelve Data (historique) + FRED (macro)
        └── report.py       rendu lisible
```

Choix de conception : les indicateurs sont **recalculés depuis les bougies
OHLCV**, pas lus depuis les indicateurs affichés sur le graphique. C'est plus
robuste (l'API d'ajout d'indicateurs du pont est cassée avec TradingView
Desktop 3.3.0) et ça permet d'analyser n'importe quel timeframe sans toucher
au graphique de l'utilisateur.

Les calculs sont validés contre TradingView : la moyenne de Wilder (`rma`),
qui sous-tend RSI / ATR / ADX, correspond aux valeurs du Williams Alligator
affiché à **0,0001 %** près.

## Utilisation

```bash
python3 -m gold_agent
```

Options :

| Option | Effet |
|---|---|
| `--json` | sortie JSON brute (pour chaîner avec autre chose) |
| `--symbol SYM` | analyser un autre symbole (défaut `FOREXCOM:XAUUSD`) |
| `--bars N` | nombre de bougies par timeframe (max 500) |
| `--no-context` | ignore le contexte macro DXY — plus rapide |
| `--m1` | ajoute le timeframe M1 (exécution) avec détection des FVG |
| `--draw` | trace les zones sur le graphique TradingView |
| `--clear-draw` | efface uniquement les tracés de l'agent |

L'agent relance TradingView automatiquement si le CDP ne répond pas, et
restaure le symbole et le timeframe d'origine du graphique en fin d'analyse.

## Le débat contradictoire

Architecture inspirée de [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
(Apache-2.0). Leur code n'est pas utilisé — il est conçu pour des actions
(bilans, résultats, sentiment par ticker), ce que l'or n'a pas. C'est
l'architecture qui a été portée, et recalibrée pour l'or.

Le principe : au lieu d'un score unique qui compense les signaux entre eux,
deux thèses opposées sont construites **séparément** à partir des mêmes
données. Un score unique masque les contre-arguments ; une tendance haussière
en surachat extrême produit un score positif qui cache que la moitié des
éléments plaide pour attendre.

Un **garde-fou de risque** arbitre ensuite, et peut opposer son veto au camp
gagnant. Son rôle n'est pas de choisir la direction mais de dire si la
configuration est exploitable :

| Veto | Déclenchement |
|---|---|
| Conflit Daily/H4 | Le contexte et le biais de session se contredisent |
| Marché en range | ADX sous 20 sur tous les timeframes |
| Extension extrême | RSI ≥ 70 **et** prix à plus de 5 % de l'EMA50 |

| Réserve | Déclenchement |
|---|---|
| Divergence contraire | Divergence RSI 1D ou H4 contre la thèse gagnante |
| Stop trop large | Invalidation à plus de 3 ATR H4 |
| Unanimité suspecte | Aucun contre-argument trouvé — signale un angle mort |
| Conviction faible | Répartition des poids proche de 50/50 |

Les timeframes sont pondérés (1D ×3, H4 ×2, H1 ×1) : un signal H1 ne renverse
pas une structure Daily.

## Ce que produit l'analyse

- **Par timeframe** (1D contexte, H4 biais, H1 timing) : structure de marché,
  biais scoré, force de tendance (ADX), EMA50/200, RSI, ATR, supports et
  résistances groupés par proximité.
- **Synthèse** : alignement ou conflit entre timeframes, niveau d'invalidation.
- **Alertes d'extension** : surachat/survente et écart à l'EMA50, pour éviter
  d'entrer au sommet d'un mouvement étiré.
- **Divergences RSI** : le prix fait un nouveau sommet, le momentum non.
- **Débat contradictoire** : thèse haussière et thèse baissière pondérées,
  puis verdict du garde-fou de risque.
- **Contexte macro** : DXY (corrélation inverse à l'or).

## Prérequis

- TradingView Desktop installé
- Node.js 18+, Python 3.9+
- **`TVD_DEBUGMODE=true` est obligatoire** sur TradingView Desktop v3.x :
  sans cette variable l'app ouvre le port CDP mais refuse toute connexion.
  Le script `~/claudeverstradingview/scripts/launch_tv_debug_mac.sh` a été
  corrigé en conséquence.

## Le timeframe M1

`--m1` ajoute un timeframe d'exécution avec **détection des Fair Value Gaps**
(déséquilibres à trois bougies) et leur état de comblement. Un FVG déjà comblé
est écarté ; seuls les non comblés sont retenus, triés par proximité au prix.

Trois adaptations, parce que le M1 n'obéit pas aux mêmes règles :

- **Périodes courtes** (EMA20/50 au lieu de 50/200). Sur 300 bougies M1, une
  « EMA200 » ne couvre que 3 h — l'appeler tendance de fond serait un abus.
- **Poids nul dans le débat directionnel.** Le M1 sert au timing, pas à
  décider du sens. La direction vient du Daily et du H4.
- **Veto d'extension désactivé** en M1 : le RSI y sature en permanence, le
  veto se déclencherait à chaque bougie.

Le tracé se recadre automatiquement quand `--m1` est actif : les niveaux à
plus de 30 ATR M1 (~29 points) sont écartés, sinon les zones Daily écrasent
l'échelle et rendent les FVG invisibles.

## Détection de motifs (`patterns.py`)

Quatre détecteurs, tous déterministes et calculés depuis les bougies.

**Zigzag** — points de retournement séparés d'au moins 2 ATR. Approche par
seuil de renversement plutôt que par fractales : une jambe n'est validée que
si le prix s'est retourné d'une amplitude significative. Deux invariants sont
garantis : alternance stricte sommet/creux, et index strictement croissants
(pas de jambe de zéro bougie).

**Vagues d'Elliott** — étiquetage 1-2-3-4-5 des cinq dernières jambes, validé
contre les **trois règles strictes** :

| Règle | Contrainte |
|---|---|
| R1 | La vague 2 ne retrace jamais plus de 100 % de la vague 1 |
| R2 | La vague 3 n'est jamais la plus courte de 1, 3, 5 |
| R3 | La vague 4 n'entre jamais dans le territoire de la vague 1 |

Si une règle est violée, **aucun comptage n'est renvoyé** — la violation est
affichée à la place. Le comptage automatique d'Elliott est intrinsèquement
ambigu ; mieux vaut ne rien afficher qu'afficher une lecture fausse. Un
comptage valide n'est pas pour autant certain : plusieurs comptages
compatibles coexistent souvent.

**Order blocks** — dernière bougie de sens opposé avant un déplacement de plus
de 2 ATR en 5 bougies. La zone retenue est le corps (open-close), pas la
mèche. Trois états : `actif`, `mitige` (prix revenu à plus de 50 % dans la
zone), `casse` (prix traversé de part en part — la zone ne fait plus réaction).

**Sessions** — plages haute/basse par séance en UTC (Asie 0-8h, Londres 8-16h,
New York 13-21h). Calculées sur le H1, pas le M1 : 300 bougies M1 ne couvrent
que 6 h, soit une seule séance. Le créneau 21h-00h UTC n'est rattaché à aucune
séance.

## Calculateur de position

L'agent ne choisit **jamais** de niveau d'entrée, d'objectif ou de stop — ce
serait une recommandation de transaction. Il fournit en revanche
l'arithmétique une fois que tu as choisi les tiens :

```bash
python3 -m gold_agent.calc --entree 4673.88 --stop 4665 --capital 10000 --risque 1
```

Sortie : sens déduit, distance du stop exprimée en ATR de chaque timeframe,
taille de position en lots et en onces, valeur du point, et **R:R vers chaque
niveau structurel détecté** par la dernière analyse (supports, résistances,
FVG, order blocks, hauts/bas de session, invalidation).

| Option | Rôle |
|---|---|
| `--entree` | ton prix d'entrée (obligatoire) |
| `--stop` | ton stop-loss (obligatoire) |
| `--capital` | capital du compte (obligatoire) |
| `--risque` | risque en % du capital, défaut 1 |
| `--tp` | ton objectif, si tu en as un — vérifie sa cohérence et calcule son R:R |

Le calculateur lit le dernier rapport d'analyse, sauvegardé automatiquement
dans `~/.gold_agent_last.json`. Lance une analyse avant de l'utiliser.

Contrôles de cohérence : refus si entrée = stop, et alerte si le TP fourni est
du mauvais côté de l'entrée pour le sens détecté.

## Règle mécanique et backtest

La règle ne relève d'aucun jugement : elle prend les bougies et sort des
niveaux, toujours de la même façon.

```
Filtre       EMA rapide > EMA lente et prix > EMA lente (tendance)
Veto         RSI ≥ 70 ET prix étiré de ≥ 5 % de l'EMA rapide
Déclencheur  la mèche touche un support confirmé (< 0,5 ATR)
Entrée       au niveau du support
Stop         entrée − 1,5 × ATR
Objectif     première résistance confirmée au-dessus, si R:R ≥ 1,5
Sortie       premier des deux touché, abandon après 40 bougies
```

La version vendeuse est le miroir exact.

```bash
python3 -m gold_agent.backtest --tf 60 --rr-min 1.5 --k-stop 1.5
```

### Les trois précautions qui rendent le chiffre honnête

**Anti-lookahead.** Un pivot n'est connu qu'après ses bougies de confirmation,
et le filtre de tendance s'évalue sur la bougie **précédente** — l'entrée sur
limite se remplit pendant la bougie courante, donc avant que sa clôture soit
connue. Sans cette précaution, la même règle affichait 83 % de réussite et
+1,21R d'espérance ; avec, elle tombe à 50 % et +0,28R.

**Une position à la fois.** Un même support touché sur plusieurs bougies
consécutives génère plusieurs signaux identiques. Les compter séparément
duplique gains et pertes et gonfle l'échantillon.

**Bougie ambiguë comptée en perte.** Si une bougie touche stop et objectif,
on compte la perte : sans données infra-bougie, impossible de savoir lequel
est arrivé en premier.

### Quatre corrections qui ont chacune réduit les résultats

| Correction | Effet mesuré |
|---|---|
| Lookahead du filtre de tendance | 83 % → 50 % de réussite, +1,21R → +0,28R |
| Doublons (une position à la fois) | 5 « trades » → 2 trades réels |
| Coût de transaction (0,3 pt) | −0,03R d'espérance |
| **Remplissage réaliste** | trades divisés par ~2, espérance −30 % |

Le remplissage était le plus important : la condition acceptait un creux
s'arrêtant *au-dessus* du support, et enregistrait une entrée à un prix jamais
traité. Un ordre limite n'aurait pas été rempli.

### Résultats sur ~3 ans de H4 (nov. 2023 → août 2026)

```bash
python3 -m gold_agent.backtest --source twelvedata --tf 240 --bars 5000
```

| Config | Trades | Profitables | Espérance | Facteur profit | Pire creux |
|---|---|---|---|---|---|
| EMA50/200 k1,0 | 70 | 51,4 % | +0,656R | 2,32 | −4,11R |
| EMA20/50 k1,0 | 69 | 50,7 % | +0,645R | 2,28 | −5,16R |

**8 configurations sur 8 en espérance positive**, et positives sur les **trois
tiers** de la période prise séparément.

### La réserve qui compte plus que les chiffres

La répartition par sens est sans appel :

| Sens | Trades | Profitables | Espérance | Cumul |
|---|---|---|---|---|
| Achat | 65 | 53,8 % | +0,743R | +48,3R |
| Vente | **5** | 20,0 % | −0,475R | −2,4R |

**Tout l'avantage vient du côté acheteur**, mesuré sur une période où l'or a
connu une hausse historique. Le filtre de tendance n'a presque jamais autorisé
de vente. Le côté vendeur est donc **non testé**, et la règle revient à
« acheter les replis d'un marché haussier » — ce qui fonctionne tant que le
marché est haussier. Sa tenue dans une baisse durable de l'or reste inconnue.

## Sources de données externes

Le pont TradingView plafonne à 300 bougies, ce qui rend tout backtest
statistiquement vide. Deux sources gratuites lèvent la limite.

```bash
cp .env.example .env      # puis colle tes clés dans .env
```

| Variable | Où l'obtenir | Usage |
|---|---|---|
| `TWELVEDATA_API_KEYS` | [twelvedata.com/pricing](https://twelvedata.com/pricing) | une ou plusieurs clés séparées par des virgules |
| `FRED_API_KEY` | [fredaccount.stlouisfed.org/apikeys](https://fredaccount.stlouisfed.org/apikeys) | taux réels US (`DFII10`) |

```bash
python3 -m gold_agent.backtest --source twelvedata --tf 60 --bars 5000
```

`.env` est dans `.gitignore`. Les clés sont lues depuis le fichier ou
l'environnement — elles ne transitent jamais par la conversation.

Note technique : le transport passe par `curl` et non `urllib`, car
l'installation Python 3.14 de cette machine n'a pas ses certificats CA
(`CERTIFICATE_VERIFY_FAILED`). La vérification TLS reste active — elle n'est
jamais désactivée. Pour corriger Python proprement :
`/Applications/Python\ 3.14/Install\ Certificates.command`

Yahoo Finance et Stooq sont inutilisables : le premier renvoie 429 depuis cet
environnement, le second oppose un défi anti-robot.

## Détection de régime (`regime.py`)

Ajouté après un renversement de 87 points sur l'or (25/08/2026) qui a révélé
trois défauts dans le garde-fou.

**Le veto d'extension était une falaise.** Il exigeait `RSI ≥ 70` **ET**
`écart ≥ 5 %`. Avec un RSI à 69,1, toute la protection s'éteignait alors que
le prix restait étiré à +7,3 % de son EMA. Remplacé par un **score gradué
0-100** : l'écart à l'EMA vaut jusqu'à 60 points (saturation à 8 %), le RSI
jusqu'à 40 (à partir de 55). Passer de 69 à 70 ne change plus rien de brutal.

| Situation | RSI | Écart | Score | Ancien veto |
|---|---|---|---|---|
| 24/08 | 72,9 | +8,3 % | 88,6 extrême | ACTIF |
| 25/08 | 69,1 | +7,3 % | **77,5 extrême** | **éteint** |

**Le garde-fou contredisait la synthèse.** Il annonçait « conviction nette,
sans objection » pendant que la synthèse disait « MIXTE, pas d'alignement
franc ». Une synthèse mixte dégrade désormais la conviction.

**L'agent n'avait aucune mémoire du régime.** Deux détecteurs ajoutés :

- `regime_volatilite` — ratio ATR court / ATR long. Au-delà de 1,5, les stops
  calibrés sur la période précédente sont trop serrés.
- `renversement` — mesure le rejet (extrême atteint moins clôture) en ATR. La
  structure en pivots, plus lente, ne l'enregistre pas encore.

## Filtre multi-timeframe

La règle ne consultait que son propre timeframe. Un achat M5 se déclenchait
alors que le Daily était en abstention. `facteur_superieur` agrège N bougies
pour reconstituer le timeframe supérieur sans requête supplémentaire — et
n'utilise que la dernière bougie agrégée **entièrement fermée**, la bougie en
cours étant incomplète.

| Timeframe | Sans | Avec | Trades |
|---|---|---|---|
| M5 → H1 | +0,125R | +0,194R | 32 → 28 |
| H1 → H4 | +0,559R | +0,582R | 38 → 26 |
| H4 → Daily | +0,656R | +0,705R | 70 → 68 |

Amélioration réelle mais modeste. Le **pire creux est inchangé** sur les trois :
le filtre écarte des trades marginaux, il ne protège pas des mauvaises séries.

## Filtres de surachat / survente

La règle contenait la **même falaise** que le garde-fou : elle n'écartait un
achat que si `RSI ≥ 70` **ET** `écart ≥ 5 %`. Un RSI à 69 ne bloquait rien.
Remplacé par un seuil simple sur le RSI, actif par défaut.

| Timeframe | Sans filtre | RSI max 70 | Pire creux |
|---|---|---|---|
| H4 | +0,705R | **+0,762R** | −4,11R → **−3,10R** |
| H1 | +0,582R | +0,757R | −4,07R → **−3,05R** |
| M5 | +0,194R | inchangé | inchangé |

Le gain principal est la **réduction du pire creux d'environ 25 %** — ce que le
filtre multi-timeframe n'avait pas obtenu. Sans effet en M5 : les entrées sur
support y ont rarement un RSI élevé.

Un seuil à 65 dégrade le H4 (+0,501R) mais améliore le H1 (+0,842R). Réglable
via `--rsi-max-achat` / `--rsi-min-vente` ; `100` et `0` désactivent.

## Tableau de bord

```bash
python3 -m gold_agent.web
```

Ouvre `http://127.0.0.1:8787` automatiquement. Quatre timeframes côte à côte —
H4, H1, M30, M15 — avec pour chacun : les zones entrée / stop / take profit
quand la règle produit un signal, la raison du refus sinon, les indicateurs
(RSI, ATR, score d'extension), les alertes de régime, et un graphique en
chandeliers dessiné en SVG avec les zones superposées.

`/json` renvoie les mêmes données brutes.

**Chaque carte porte un badge de fiabilité** indiquant ce que le backtest a
réellement mesuré sur ce timeframe :

| Badge | Timeframe | Base |
|---|---|---|
| mesuré | H4 | 64 trades, 3 ans, +0,762R |
| indicatif | H1 | 22 trades, échantillon faible |
| non mesuré | M30, M15 | jamais backtesté |

Un signal M15 s'affiche comme un signal H4, mais le badge rouge dit qu'aucune
preuve ne le soutient. C'était le principal risque de ce genre d'interface :
donner la même autorité visuelle à des choses très inégalement établies.

### Exécution automatique : non

Le projet **ne passe aucun ordre** et n'en passera pas. Les signaux sont
notifiés, jamais exécutés. Deux raisons au-delà du principe :

- La règle est validée sur **64 trades, côté acheteur uniquement**, pendant une
  hausse historique de l'or. Le côté vendeur affiche une espérance négative sur
  5 trades. Le M30 et le M15 n'ont aucun backtest.
- Le paquet Python `MetaTrader5` **n'existe pas pour macOS** — il est publié
  uniquement pour Windows. MT5 sur Mac tourne via Wine, sans pont Python natif.

### Push vers le téléphone

`notify.py` envoie chaque signal sur trois canaux, avec un **ticket d'ordre
prêt à saisir** dans MetaTrader 5 mobile :

```
Symbole   XAUUSD
Type      Sell Limit
Prix      4631.91
SL        4643.15
TP        4613.18
R:R       1.67
Volume    0.43 lot  (risque 100.0 = 1% de 10000)
```

| Canal | Portée |
|---|---|
| Navigateur + bip | onglet ouvert, bridé en arrière-plan |
| Système (`osascript`) | même navigateur fermé, macOS |
| Push (`ntfy.sh`) | **téléphone, où que tu sois** |

Configuration dans `.env` :

| Variable | Rôle |
|---|---|
| `NTFY_TOPIC` | sujet ntfy — quiconque le connaît lit les messages, garde-le privé |
| `CAPITAL` | capital du compte, pour calculer le volume en lots |
| `RISQUE_PCT` | risque par trade en % (défaut 1) |

Le ticket porte les avertissements du signal : timeframe non backtesté, côté
vendeur non validé. Ils voyagent avec la notification plutôt que de rester
dans le README.

### Rafraîchissement et notifications

La page se met à jour **toute seule toutes les 30 s**, sans rechargement : le
serveur renvoie données et fragment HTML dans la même réponse `/json`, le
navigateur remplace les cartes. Un compteur indique le prochain contrôle.

Deux canaux de notification, volontairement redondants :

| Canal | Portée | Limite |
|---|---|---|
| Navigateur (`Notification` + bip) | onglet ouvert | **les navigateurs bridient les minuteurs en arrière-plan** — jusqu'à 1 exécution/minute |
| Système (`osascript`) | même navigateur fermé | macOS uniquement |

Le second existe précisément parce que le premier faiblit quand on en a le
plus besoin : quand on ne regarde pas l'écran.

Une notification par configuration, jamais de répétition à chaque sondage.
L'identité d'un signal inclut son prix d'entrée — si la règle déplace son
niveau, c'est un nouveau signal. Le premier passage amorce la liste **sans
notifier**, sinon un signal déjà présent au démarrage déclencherait une alerte
trompeuse.

```bash
python3 -m gold_agent.web                      # surveillance toutes les 5 min
python3 -m gold_agent.web --surveillance 0     # tableau seul, sans surveillance
python3 -m gold_agent.web --surveillance 120   # plus réactif, consomme plus
```

### Prix en direct

Le prix affiché vient d'un appel `/quote` **séparé** du cache des bougies —
une seule requête, cache de 15 s. La dernière bougie (non close, donc dont la
clôture en cache est périmée) est **réalignée sur ce prix avant l'analyse** :
les niveaux, les distances et les R:R portent sur le prix réel, pas sur une
clôture vieille de plusieurs minutes.

Séparer les deux permet d'allonger fortement le cache des bougies — la
structure bouge lentement, le prix non :

| | Avant | Maintenant |
|---|---|---|
| H4 | 6 min | 12 min |
| H1 | 3 min | 6 min |
| M30 | 2 min | 4 min |
| M15 | 1 min | 2 min |
| **Prix** | = clôture en cache | **15 s** |
| Consommation | 2880/jour (72 %) | **1440/jour (36 %)** |

Le prix est plus frais *et* la consommation a été divisée par deux.

### Quota restant

`/api_usage` est interrogé clé par clé (cache 5 min) et donne la consommation
**réelle du jour**, toutes sessions confondues — le compteur interne ne voyait
que la session en cours. Une jauge en tête de page affiche les requêtes
restantes ; l'infobulle détaille clé par clé, y compris la limite par minute.

### Rotation de clés

`TWELVEDATA_API_KEYS` accepte plusieurs clés séparées par des virgules. Chaque
requête prend la suivante à tour de rôle : la charge se répartit au lieu
d'épuiser la première. Une clé qui renvoie une erreur de quota est mise au
repos 65 s (la limite Twelve Data est par minute) et la suivante prend le
relais sans faire échouer l'appel.

**Une panne serveur n'est pas une erreur de quota.** Les 502 et 503 sont
traités séparément : on rejoue la *même* clé après une pause croissante, au
lieu de brûler les autres pour rien. Sans cette distinction, un hoquet de
Twelve Data mettait les cinq clés au repos d'un coup.

Les durées de cache s'adaptent au nombre de clés — le quota cumulé permet de
les raccourcir :

| Clés | Quota/jour | H4 | H1 | M30 | M15 | Consommation |
|---|---|---|---|---|---|---|
| 1 | 800 | 30 min | 15 min | 10 min | 5 min | 576 (72 %) |
| 5 | 4000 | 6 min | 3 min | 2 min | 1 min | 2880 (72 %) |

Un plancher empêche de descendre sous la durée de formation de la bougie :
rafraîchir du H4 toutes les 10 s n'apporte rien.

`/json` expose l'usage par clé et le total de la session.

### Cache

Twelve Data limite le plan gratuit à 8 requêtes/minute et **800/jour**. Chaque
collecte consomme 4 requêtes. Deux profils de durée de vie, parce que la
surveillance continue et la consultation n'ont pas les mêmes contraintes :

| Profil | H4 | H1 | M30 | M15 | Consommation |
|---|---|---|---|---|---|
| consultation | 5 min | 3 min | 2 min | 1 min | 2928/jour — **3,7× le quota** |
| surveillance | 30 min | 15 min | 10 min | 5 min | 576/jour — 72 % du quota |

Le profil surveillance s'active automatiquement avec `--surveillance`. Sans
cet allongement, le quota saute en quelques heures de fonctionnement continu.

Un compteur de requêtes est exposé dans `/json` et affiché à l'arrêt du
serveur — sans suivi, on ne découvre le dépassement qu'au moment où tout casse.

En cas d'échec réseau, la dernière donnée connue est réutilisée et **signalée
comme figée** — une carte datée mais annoncée vaut mieux qu'une carte vide.

## Limites connues

- `indicator add` du pont ne fonctionne pas avec TradingView Desktop 3.3.0
  (le registre d'études a changé). Sans impact : l'agent calcule ses propres
  indicateurs.
- Le volume est nul sur `FOREXCOM:XAUUSD` (spot). Utiliser `TVC:GOLD` ou les
  futures GC pour une analyse volumétrique.
- **Historique M1 limité à 300 bougies (6 h)** par le plan de données
  TradingView. Faire défiler le graphique ne charge pas plus.
- **L'ATR M1 sur l'or est d'environ 0,9 point.** Certains FVG détectés font
  0,4 point, soit à peine plus que le spread. À filtrer selon ton courtier.
- Les order blocks sont fréquemment tous à l'état `casse` en tendance forte :
  le prix traverse les zones sans y réagir. C'est une information, pas un bug.
- Le dézoom programmatique du graphique ne fonctionne pas de façon fiable —
  zoomer à la molette pour voir le zigzag et les sessions.
- Chaque appel CLI relance un process Node et rouvre une connexion CDP
  (~3-5 s). Une analyse complète prend environ 60-90 s.
# TradingBotSignal
# TradingBotSignal
