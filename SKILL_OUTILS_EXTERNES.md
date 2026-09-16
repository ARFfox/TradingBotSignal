# Skill `outils-externes` — que prendre, que laisser

> À placer dans `.claude/skills/outils-externes/SKILL.md`
> Évaluation des 10 dépôts du carrousel, au 16/09/2026.

---

## La règle avant la liste

Ton système a **288 trades résolus, −77,98R, et aucun walk-forward**.

Aucun de ces dépôts ne corrige ça. Un outil ne crée pas d'edge — il exécute
plus vite une stratégie qui en a un, ou qui n'en a pas. Ajouter FinRL à un
système à −78R, c'est mettre un réacteur sur une voiture sans freins.

Cela dit, **deux d'entre eux débloquent un problème réel que tu as
aujourd'hui**, et un troisième vaut pour une idée d'architecture. Les sept
autres sont hors sujet pour ton projet. Le tri est ci-dessous.

---

## 1. 🔴 CCXT — à prendre, il remplace du code que tu maintiens

> *Une API unifiée pour 100+ exchanges crypto.*

C'est exactement ce que `feeds/binance.py` et `feeds/bybit.py` font à la
main. CCXT le fait pour 100 plateformes, est maintenu par une communauté
large, et gère à ta place les rate limits, les reconnexions WebSocket et les
formats de symbole propres à chaque exchange — trois choses qui cassent
silencieusement quand on les écrit soi-même.

```python
import ccxt
ex = ccxt.binance()
bougies = ex.fetch_ohlcv("BTC/USDT", "1h", limit=1000)
```

**Gain concret :** supprime ~300 lignes d'adaptateurs et les bugs de
reconnexion que tu n'as pas encore rencontrés.

⚠️ **Crypto uniquement.** Le forex, les matières premières et les actions
restent sur yfinance / Twelve Data. CCXT ne les couvre pas.

---

## 2. 🔴 VectorBT — à prendre, il débloque ton vrai blocage

> *Backtesting vectorisé, des milliers de combinaisons en secondes.*

C'est **le** outil qui répond à la question que ton système ne peut pas
trancher aujourd'hui : *existe-t-il un réglage où ce système gagne ?*

Ton `parametres_agents.py` teste un paramètre à la fois, en Python pur. Pour
balayer (60 instruments × 4 TF × 15 valeurs de stop × 4 découpes), il faudrait
des heures. VectorBT fait ça en secondes parce qu'il travaille sur des
matrices NumPy au lieu de boucler.

```python
import vectorbt as vbt
# balaye 15 multiples d'ATR sur tous les instruments d'un coup
pf = vbt.Portfolio.from_signals(prix, entrees, sorties,
                                sl_stop=multiples, fees=0.0005, slippage=0.0002)
pf.total_return()          # une valeur par combinaison
```

⚠️ **Et c'est précisément là que se trouve le danger.** Tester 3 600
combinaisons en 10 secondes rend le sur-apprentissage *trivial* : une
centaine paraîtra excellente par pur hasard. **VectorBT ne remplace pas le
protocole walk-forward de `parametres_agents.py` — il l'alimente.** Tu
cherches avec VectorBT sur le train, tu juges avec ton protocole sur le test.
Utilisé sans ce garde-fou, cet outil est le moyen le plus rapide de se
convaincre qu'on a trouvé quelque chose.

**Noter aussi :** `fees` et `slippage` sont des paramètres, pas des options.
Un backtest sans eux ment sur du M5.

---

## 3. 🟠 TradingAgents — à lire, pas à installer

> *Framework multi-agents LLM. C'est celui que tu m'as envoyé.*

### Ce que le dépôt dit vraiment

J'ai lu le README plutôt que l'infographie. Les auteurs écrivent eux-mêmes :

> *« Le framework est conçu à des fins de recherche. Ce n'est pas un conseil
> financier. » · « Les résultats de backtest ne correspondront pas
> nécessairement aux chiffres publiés. » · « Traitez-le comme un échafaudage
> de recherche pour étudier l'analyse multi-agents, pas comme une stratégie
> au rendement fixe et reproductible. »*

**Aucun résultat hors échantillon n'est publié.** Les auteurs sont honnêtes ;
c'est le carrousel Instagram qui ne l'est pas.

Ils signalent aussi que les résultats sont **non déterministes** : deux
exécutions sur les mêmes données donnent des réponses différentes
(échantillonnage du modèle, données live, volatilité des réseaux sociaux).
Pour un système de décision, c'est une propriété lourde de conséquences —
tu ne peux pas backtester ce qui ne se reproduit pas.

### L'idée qui vaut vraiment d'être reprise

Leur structure : une équipe d'analystes, puis **deux chercheurs, un haussier
et un baissier, qui doivent débattre**, puis un trader, puis une équipe
risque qui approuve ou rejette.

Compare à ton système : tu as l'**Avocat du diable** (AG-16) qui argumente
toujours CONTRE. Il te manque **l'avocat qui argumente POUR**.

Aujourd'hui ton Chef arbitre entre un procureur et un silence. C'est
déséquilibré : personne n'est chargé de construire le meilleur dossier en
faveur du signal, donc les objections ne sont jamais vraiment testées.

**AG-18 Avocat de la défense** — symétrique de AG-16 :

| | AG-16 Avocat du diable | AG-18 Avocat de la défense |
|---|---|---|
| Rôle | construit le meilleur dossier CONTRE | construit le meilleur dossier POUR |
| Vote | toujours négatif | toujours positif |
| Valeur | force à justifier l'entrée | force à justifier le rejet |

Le Chef n'arbitre plus « une objection contre rien », mais **deux dossiers
construits**. C'est une vraie amélioration de ton architecture, et elle ne
demande pas d'installer quoi que ce soit.

### Le coût, qui décide de tout

Un débat LLM sur chaque signal candidat, sur 60 instruments × 4 timeframes,
en continu, représente des milliers d'appels par jour. Ce n'est pas tenable.

**La seule utilisation viable :** le débat ne se déclenche **qu'après** la
porte mécanique — sur les signaux qui ont déjà passé le seuil, l'espérance
du couple, le stop minimum et l'anti-contradiction. Ça fait 5 à 10 débats
par jour au lieu de milliers, et ça place le raisonnement coûteux là où il
change une décision.

---

## 4. 🟡 À connaître, pas pour maintenant

| Outil | Ce que c'est | Quand ça deviendra pertinent |
|---|---|---|
| **Backtrader** | backtesting événementiel, mature | jamais pour tes balayages — VectorBT est 100× plus rapide sur ce besoin. Le projet est peu actif. |
| **NautilusTrader** | moteur institutionnel, 0,3 ms de latence | le jour où tu passes à l'exécution réelle. Aujourd'hui tu n'exécutes rien : c'est de l'infrastructure sans usage. |
| **Lumibot** | build / backtest / deploy, plus simple | alternative plus accessible que Nautilus, même échéance |
| **Freqtrade** | bot crypto avec hyperopt | crypto uniquement. Son **hyperopt avec walk-forward** est une bonne référence à lire, même sans l'adopter. |

---

## 5. ❌ Hors sujet pour ton projet

**Hummingbot** — market making et arbitrage. Un métier entièrement
différent : gagner le spread en cotant des deux côtés, pas prédire une
direction. Rien à voir avec ce que tu construis.

**Polymarket API** — marchés de prédiction (« qui gagne l'élection »).
Intéressant, mais c'est une autre classe d'actifs avec ses propres règles.
Une distraction tant que le système principal perd de l'argent.

**FinRL** — apprentissage par renforcement profond. 🔴 **Le plus dangereux
de la liste pour toi.**

> Un agent RL a typiquement des dizaines de milliers de paramètres. **Tu as
> 288 trades résolus.** Entraîner ça revient à demander à un modèle de
> mémoriser ton historique, pas d'en tirer une règle. Il affichera une
> courbe magnifique sur tes données et perdra sur les suivantes — et
> contrairement à une moyenne mobile mal réglée, tu ne pourras pas
> comprendre pourquoi.

Le RL en finance demande des années de données tick et une équipe qui sait
diagnostiquer un surapprentissage. Ce n'est pas une question de niveau, c'est
une question de volume de données. Reviens-y si tu atteins un jour plusieurs
dizaines de milliers de trades.

---

## 6. Ordre d'adoption

| # | Quoi | Pourquoi maintenant |
|---|---|---|
| 1 | **CCXT** dans `feeds/` | supprime du code fragile, gain immédiat |
| 2 | **VectorBT** dans `research/walkforward.py` | rend possible le balayage que tu ne peux pas faire |
| 3 | **AG-18 Avocat de la défense** | équilibre le débat, zéro dépendance |
| 4 | **Débat LLM après la porte mécanique** | uniquement si 1-3 sont en place et que le système est positif |
| — | tout le reste | quand le système gagne |

**Les étapes 1 à 3 ne demandent aucune décision stratégique.** L'étape 4 n'a
de sens que si les précédentes ont donné un système à espérance positive —
un débat sophistiqué sur un signal sans edge produit une mauvaise décision
bien argumentée.

---

## 7. Ce qu'il faut retenir du carrousel lui-même

Les dix fiches affichent des courbes qui montent, des Sharpe entre 1,42 et
1,92 et des taux de réussite entre 61 % et 64 %. **Ce sont des illustrations
marketing, pas des résultats mesurés** — VectorBT et Backtrader sont des
bibliothèques : elles n'ont pas de performance, elles calculent celle de ce
qu'on leur donne. Afficher « +128 % de rendement » pour une bibliothèque de
backtest n'a aucun sens.

Le compte qui publie ces fiches vend de l'audience. Les outils sont réels et
certains sont excellents — mais les chiffres collés dessus ne décrivent rien.

Ton seul chiffre vérifiable reste **−77,98R sur 288 trades**, et c'est lui
qui doit guider les décisions.

---

## Sources

- [TradingAgents — dépôt GitHub](https://github.com/TauricResearch/TradingAgents)
- [TradingAgents: Multi-Agents LLM Financial Trading Framework — arXiv 2412.20138](https://arxiv.org/abs/2412.20138)
- [Page du projet TradingAgents](https://tauricresearch.github.io/TradingAgents/)
