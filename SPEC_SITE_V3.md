# Refonte du site — spécification pour Claude Code

> À exécuter avec `SYSTEME.md`. Sept changements, dans l'ordre.
> `python3 verif.py` après chacun. Ne pas passer au suivant sur du rouge.

---

## Vue d'ensemble

| # | Changement | Fichiers |
|---|---|---|
| 1 | Registre d'instruments unique (~60 actifs, 4 marchés) | `core/instruments.py` (nouveau) |
| 2 | Navigation fluide : marché → instrument → tout suit | `web.py`, front |
| 3 | En-tête + TradingView qui basculent ensemble | `web.py`, front |
| 4 | Pastilles en cascade depuis UNE seule liste | `tableau.py`, front |
| 5 | Timeframes en boutons | front |
| 6 | Cases d'agents reliées au Superviseur (sans icônes) | front |
| 7 | Onglet « Signaux validés » à la place de « Historique » | `journal.py`, front |

---

## 1. Le registre d'instruments

Tout part de là. Créer `core/instruments.py` :

```python
@dataclass(frozen=True)
class Instrument:
    cle: str            # "XAUUSD" — identifiant interne, jamais affiché
    libelle: str        # "XAU/USD" — ce que voit l'utilisateur
    nom: str            # "Or"
    marche: str         # "matieres" | "forex" | "crypto" | "actions"
    tv: str             # "OANDA:XAUUSD"  <-- symbole TradingView
    td: str | None      # "XAU/USD"       <-- symbole Twelve Data
    yf: str             # "GC=F"          <-- symbole yfinance
    binance: str | None # "BTCUSDT"       <-- symbole Binance (crypto)
    decimales: int      # 2
    valeur_point: float # pour le sizing — JAMAIS une constante globale
    tick: float
```

### ⚠️ Le piège numéro un : les symboles TradingView

Un widget TradingView ne comprend pas `"XAU/USD"`. Il exige un symbole
**préfixé par la place** :

| Ce que tu affiches | Ce que TradingView exige |
|---|---|
| XAU/USD | `OANDA:XAUUSD` |
| EUR/USD | `OANDA:EURUSD` |
| BTC | `BINANCE:BTCUSDT` |
| Apple | `NASDAQ:AAPL` |
| S&P 500 | `AMEX:SPY` |
| Pétrole WTI | `TVC:USOIL` |

**Si ce champ n'existe pas dans l'Instrument, le graphique restera bloqué sur
l'or quoi qu'on clique** — et ce sera très long à diagnostiquer depuis le
front. Chaque instrument porte ses quatre identifiants dès le premier jour.

### L'univers (~60)

```
MATIÈRES (10)  XAUUSD XAGUSD XPTUSD XPDUSD HG(cuivre) WTI BRENT
               GAZ BLE MAIS
FOREX (14)     EURUSD GBPUSD USDJPY USDCHF AUDUSD NZDUSD USDCAD
               EURJPY GBPJPY EURGBP EURAUD AUDJPY CHFJPY DXY
CRYPTO (14)    BTC ETH SOL BNB XRP ADA AVAX LINK DOT MATIC
               DOGE LTC ATOM NEAR
ACTIONS (18)   SPY QQQ IWM AAPL MSFT NVDA GOOGL AMZN META TSLA
               AMD NFLX JPM XOM XLE XLF XLK GDX
```

Ajouter un instrument = ajouter une ligne. Aucun code.

---

## 2. La navigation

### Un seul état, dans l'URL

```
#/matieres/XAUUSD
#/crypto/BTCUSDT
#/forex/EURUSD
```

**Tout le reste en dérive** : l'en-tête, le prix, TradingView, les
timeframes, les cartes d'agents, l'onglet signaux.

Mettre l'état dans le hash plutôt que dans une variable JavaScript a trois
conséquences concrètes : le rafraîchissement de page ne ramène pas à l'or, le
bouton retour du navigateur fonctionne, et un lien vers un instrument précis
est partageable. C'est trois lignes de code et ça évite trois bugs.

```js
function allerA(marche, cle) {
  location.hash = `#/${marche}/${cle}`;      // déclenche hashchange
}
addEventListener('hashchange', () => {
  const [, marche, cle] = location.hash.split('/');
  majEnTete(cle); majGraphique(cle); majPanneau(marche, cle);
});
```

### Les trois niveaux

```
NIVEAU 1 — barre de marchés, toujours visible en haut
  [ 🥇 MATIÈRES ③ ]  [ 💱 FOREX ]  [ 🪙 CRYPTO ② ]  [ 📈 ACTIONS ]
     ③ = 3 signaux actifs sur ce marché

NIVEAU 2 — clic sur un marché : la liste de ses instruments
  ┌──────────┬──────────┬──────────┬──────────┐
  │ XAU/USD ①│ XAG/USD  │ Platine  │ Cuivre   │
  │ 4392.37  │ 51.24    │ 1284.50  │ 5.12     │
  │ ▲ 0.42%  │ ▼ 1.10%  │ ▲ 0.08%  │ ▲ 2.31%  │
  └──────────┴──────────┴──────────┴──────────┘

NIVEAU 3 — clic sur un instrument : toute la page bascule dessus
```

---

## 3. En-tête et TradingView

### L'en-tête

```
EUR/USD   1.08423   ▲ 0.31%   ● 14:24:24 · 1 signal actif · prix en direct
```

Il lit l'instrument actif, rien d'autre. Le nombre de décimales vient de
l'Instrument : afficher `1.08` sur EUR/USD ou `4392.3700` sur l'or est faux
dans les deux sens.

### Le graphique

Pour changer de symbole, **détruire et recréer le widget** :

```js
function majGraphique(cle) {
  const inst = INSTRUMENTS[cle];
  document.getElementById('tv').innerHTML = '';
  new TradingView.widget({
    container_id: 'tv', symbol: inst.tv, interval: TF_ACTIF,
    theme: 'dark', style: 1, locale: 'fr', autosize: true,
  });
}
```

L'API `setSymbol` existe mais se comporte mal quand l'intervalle change en
même temps. Recréer le widget coûte ~300 ms et marche à tous les coups.

### ⚠️ Le prix exact — la contrainte que tu ne peux pas contourner

Tu as **800 requêtes/jour par clé Twelve Data**. 60 instruments rafraîchis
toutes les 10 s, c'est 518 400 requêtes/jour. **C'est impossible, et aucun
réglage ne le rendra possible.**

La seule architecture qui tienne :

| Où | Source | Fréquence | Coût |
|---|---|---|---|
| **Instrument actif, crypto** | Binance WebSocket | temps réel | **gratuit, illimité** |
| **Instrument actif, autre** | Twelve Data | 10 s | ~360 req/jour pour UN seul |
| **Grille (les 59 autres)** | cache yfinance | 6 h | ~0 |

Donc : **l'en-tête affiche un prix en direct, la grille affiche une clôture
différée.** La grille doit le dire — un discret « différé » sous les prix.
Afficher un prix de la veille comme s'il était en direct est le genre de
détail qui fait entrer sur un niveau qui n'existe plus.

Quand l'utilisateur change d'instrument : couper le flux précédent, ouvrir le
nouveau. Un seul flux actif à la fois.

---

## 4. Les pastilles en cascade

### Une seule liste, trois niveaux d'affichage

```python
paquet["signaux_actifs"] = [
  {"instrument": "XAUUSD", "marche": "matieres", "tf": "H1",
   "sens": "achat", "entree": 4380.5, "sl": 4358.0, "tp1": 4425.0,
   "rr": 1.98, "confiance": 0.78, "cree_ts": ..., "expire_ts": ...},
]
```

Les trois compteurs en dérivent **par calcul, jamais par duplication** :

```js
const badgeMarche    = (m) => SIGNAUX.filter(s => s.marche === m).length;
const badgeInstrument= (c) => SIGNAUX.filter(s => s.instrument === c).length;
```

C'est ce qui garantit qu'une pastille sur MATIÈRES correspond toujours à une
pastille sur un instrument précis. Deux compteurs calculés séparément finissent
toujours par diverger, et le jour où ça arrive tu ne sais plus lequel croire.

**La même liste alimente la notification ntfy.** Une seule source de vérité
pour l'écran et le téléphone.

Animation : pulsation 2 s à l'apparition, puis statique. Une pastille qui
clignote en permanence cesse d'être vue au bout de dix minutes.

---

## 5. Les timeframes en boutons

Remplacer les lignes cliquables par un sélecteur :

```
┌─────┬─────┬─────┬─────┬─────┐
│ H4  │ H1  │ M30 │ M15 │ M5  │
└─────┴─────┴─────┴─────┴─────┘
   ●     ●     ●     ○     ○      ● = émission autorisée
```

- le bouton actif est plein, les autres en contour
- un timeframe dont l'émission est coupée (`config.tf_emission`) garde son
  bouton **cliquable** — on peut regarder l'analyse — mais affiche un point
  creux et le badge `ÉMISSION OFF`
- changer de timeframe met à jour le graphique **et** le panneau d'analyse

Ne pas griser un timeframe coupé : tu veux pouvoir vérifier pourquoi il est
coupé sans avoir à le réactiver.

---

## 6. Les cases d'agents

Remplacer la démo 3D par un schéma en cases, sans icônes.

```
   PERCEPTION            MARCHÉS              RELATIONS
  ┌───────────┐      ┌───────────┐        ┌───────────┐
  │  AG-01    │      │  AG-11    │        │  AG-09    │
  │  Vigie    │──┐   │  Forex    │───┐    │Constellat.│──┐
  │  ● 90%    │  │   │  ● 20%    │   │    │  ● 100%   │  │
  └───────────┘  │   └───────────┘   │    └───────────┘  │
  ┌───────────┐  │   ┌───────────┐   │    ┌───────────┐  │
  │  AG-02    │  │   │  AG-12    │   │    │  AG-10    │  │
  │ Structure │──┤   │  Crypto   │───┤    │  Miroir   │──┤
  │  ● 26%    │  │   │  ● 100%   │   │    │  ⛔ BLOCAGE│  │
  └───────────┘  │   └───────────┘   │    └───────────┘  │
       ...       │        ...        │         ...       │
                 │                   │                   │
                 └────────┬──────────┴───────────────────┘
                          ▼
                 ┌──────────────────┐
                 │      AG-00       │
                 │   SUPERVISEUR    │
                 │  probabilité +   │
                 │   opportunité    │
                 │   ● 73%          │
                 └────────┬─────────┘
                          ▼
                 ┌──────────────────┐
                 │  SIGNAL ÉMIS     │
                 │  entrée / SL / TP│
                 └──────────────────┘
```

Règles d'affichage :
- CSS grid, traits en SVG par-dessus. Pas de moteur physique, pas d'animation
  de positionnement — les cases ne bougent pas, donc elles sont lisibles.
- point de couleur = statut : vert actif · jaune veille · **rouge blocage** ·
  gris muet
- un agent muet garde sa case, en pointillés. **Ne jamais le masquer** : une
  case absente ressemble à un agent qui n'existe pas, alors que c'est un agent
  en panne.
- le trait d'un agent qui contredit passe en jaune, celui d'un blocage en
  rouge
- clic sur une case → sa page

Le graphe force-directed de `graphe.html` peut rester dans un onglet séparé
pour explorer les corrélations. Le panneau principal, lui, doit être figé et
lisible d'un coup d'œil.

---

## 7. L'onglet « Signaux validés »

**Supprimer l'onglet « Historique » actuel et le remplacer.**

### La règle qui définit tout l'onglet

> **Seuls les signaux réellement ÉMIS y figurent** — ceux qui ont passé les
> conditions du Superviseur et qui t'ont été affichés ou notifiés.

Pas les setups détectés puis rejetés, pas les calculs intermédiaires, pas les
timeframes en `ÉMISSION OFF`. Si tu ne l'as pas vu à l'écran, il n'est pas
dans l'historique.

C'est la seule définition qui rend le taux de réussite honnête : il mesure ce
que le système t'a effectivement recommandé, pas ce qu'il aurait pu dire.

### Les états

```python
STATUTS = {
  "en_attente":   "entrée limite pas encore touchée",
  "en_cours":     "entrée touchée, ni TP ni SL atteint",
  "TP1", "TP2":   "objectif atteint",
  "SL":           "stop touché",
  "expire":       "entrée jamais touchée dans le délai — non comptabilisé",
  "invalide":     "condition d'invalidation franchie avant l'entrée",
}
```

### Le calcul du taux de réussite

```python
resolus = [s for s in signaux_emis if s.statut in ("TP1", "TP2", "SL")]
gagnants = [s for s in resolus if s.statut.startswith("TP")]
taux = len(gagnants) / len(resolus) if resolus else None
r_cumule = sum(s.r_realise for s in resolus)
```

**Trois règles non négociables :**

1. **`en_attente`, `en_cours` et `expire` ne comptent pas.** Les inclure
   dans le dénominateur ferait baisser artificiellement le taux ; les
   inclure comme gagnants le ferait monter. Ils ne sont ni l'un ni l'autre.

2. **Toujours afficher l'effectif à côté du pourcentage.** `68 %` seul est
   trompeur. `68 % sur 25 signaux résolus` est une information.
   Sous 20 signaux résolus, afficher `échantillon insuffisant` **à la place**
   du pourcentage, pas à côté. Un taux sur 3 signaux est du bruit, et
   l'afficher pousse à des décisions basées sur rien.

3. **Le R cumulé compte plus que le taux de réussite.** Un système à 40 % de
   réussite avec des gains à 3R gagne ; un système à 70 % avec des gains à
   0,5R perd. Afficher les deux, R cumulé en premier.

### La maquette

```
SIGNAUX VALIDÉS — uniquement ce qui t'a été affiché
──────────────────────────────────────────────────────────────────
   +12.4R          68 %              25 / 37              1.82
   R cumulé    taux de réussite    résolus / émis    profit factor
                 (25 résolus)
──────────────────────────────────────────────────────────────────
[ Tous ] [ Matières ] [ Forex ] [ Crypto ] [ Actions ]   [ 30j ▾ ]

Date     Instr.    TF   Sens   Entrée    SL      TP1     Résultat    R
14/09    XAUUSD    H1   achat  4380.5  4358.0  4425.0   ✅ TP1     +1.98
13/09    BTCUSDT   M30  vente  109840  110900  107200   ❌ SL      −1.00
13/09    EURUSD    H4   achat  1.0821  1.0788  1.0895   ⏳ en cours   —
12/09    XAGUSD    H1   achat  50.84   50.12   52.10    ⚪ expiré     —
──────────────────────────────────────────────────────────────────
Les signaux expirés ne comptent pas dans le taux : l'entrée n'a
jamais été touchée, il n'y a donc rien à gagner ni à perdre.
```

### Côté `journal.py`

Le journal enregistre déjà les signaux. Deux ajouts :

```python
{
  "emis": True,                    # <-- a-t-il été AFFICHÉ/NOTIFIÉ ?
  "intermarche": {"score": ..., "base": ..., "fiable": ...},
  "r_realise": float | None,
}
```

Le champ `emis` est le filtre de tout l'onglet. Le champ `intermarche` sert à
répondre, dans trois mois, à la question qui décide de tout : **est-ce que le
Miroir améliore les résultats ?** Le stocker maintenant ne coûte rien ; ne pas
le stocker rend la question définitivement sans réponse.

---

## 8. Les routes

```python
GET /api/instruments                    -> le registre complet
GET /api/instruments/{cle}              -> analyse 5 TF de cet instrument
GET /api/instruments/{cle}/prix         -> prix + variation (léger, 10 s)
GET /api/signaux/actifs                 -> LA liste qui alimente les pastilles
GET /api/signaux/valides?marche=&jours= -> l'historique + les 4 chiffres
GET /api/graphe                         -> le réseau d'agents
```

`/api/instruments/{cle}/prix` doit rester **léger** : il est appelé toutes les
10 s. Il ne recalcule rien, il lit le cache et le dernier tick.

---

## 9. Ordre de travail

| # | Étape | Vérification |
|---|---|---|
| 1 | `core/instruments.py` + les 4 symboles par actif | `verif.py` vert |
| 2 | Route `/api/instruments`, registre servi | 56 instruments en JSON |
| 3 | Barre de marchés + grille d'instruments | les listes s'affichent |
| 4 | Routage par hash + en-tête + TradingView | **clic sur EUR/USD → tout bascule** |
| 5 | Prix direct sur l'actif seul, différé sur la grille | quota Twelve Data stable |
| 6 | `signaux_actifs` + les 3 niveaux de pastilles | les 3 comptes concordent |
| 7 | Timeframes en boutons | changement instantané |
| 8 | Cases d'agents + Superviseur | lisible, agents muets visibles |
| 9 | Onglet Signaux validés | ne montre que les signaux émis |

`python3 verif.py` après chaque étape.

---

## 10. Ce qu'il ne faut pas faire

- ❌ Câbler un symbole TradingView en dur — il vient de l'Instrument
- ❌ Interroger Twelve Data pour la grille (le quota saute en une heure)
- ❌ Afficher un prix différé comme s'il était en direct
- ❌ Calculer les pastilles à deux endroits différents
- ❌ Compter les signaux expirés dans le taux de réussite
- ❌ Afficher un pourcentage sous 20 signaux résolus
- ❌ Masquer un agent muet
- ❌ Garder l'ancien historique « tous les calculs » en parallèle — il dilue
  la seule mesure qui compte

---

## 11. Le skill de stratégies

Le fichier `SKILL_STRATEGIES.md` accompagne cette spec : il formalise les
méthodes tirées des 130 captures (CRT, IFVG, Volume Profile, ORB, sessions)
en règles calculables.

**Il ne fait pas partie de cette refonte.** L'interface d'abord, les nouvelles
stratégies ensuite — et chacune passe par le backtest avant d'émettre quoi que
ce soit. Ajouter quatre familles de setups non validées à une interface qui
marche, c'est remplacer un problème visible par un problème invisible.
