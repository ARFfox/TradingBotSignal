# Skill `strategies-entree` — calcul du point d'entrée, du stop et des objectifs

> À placer dans `.claude/skills/strategies-entree/SKILL.md`
> Source : ~130 captures de `~/Documents/video`, analysées le 14/09/2026.

---

## Avertissement à lire avant d'implémenter quoi que ce soit

Les méthodes ci-dessous viennent de comptes de trading sur Instagram. Elles
sont **populaires**, ce qui n'est pas la même chose que **profitables**. Aucune
n'a d'edge démontré publiquement sur données hors échantillon.

Ce que ce skill apporte, ce n'est donc pas « voici des stratégies qui
gagnent ». C'est : **voici comment transformer ces descriptions floues en
règles mesurables**, pour que le protocole de backtest puisse enfin dire
lesquelles fonctionnent sur TES marchés et TES timeframes.

**Règle absolue : aucun de ces patterns n'émet un signal live avant d'avoir
passé le walk-forward avec coûts réels.** Le corpus sert à générer des
candidats, pas des certitudes.

---

## 1. Le contrat commun

Toute stratégie de ce skill retourne cette structure, ou `None` :

```python
@dataclass
class Setup:
    nom: str              # "CRT" | "IFVG" | "ORB" | "POC_RETEST" | ...
    sens: str             # "achat" | "vente"
    entree: float         # prix limite
    sl: float             # invalidation STRUCTURELLE, jamais un % arbitraire
    tp1: float            # premier objectif
    tp2: float | None
    rr: float             # (tp1 - entree) / (entree - sl), en valeur absolue
    zone_valide_jusqu_a: int   # horodatage d'expiration
    conditions: list[str]      # ce qui a été vérifié, une ligne par condition
    invalidation: str          # en français, ce qui tue le setup
```

**Trois règles qui ne se négocient pas :**

1. **Le stop est structurel.** Il se place derrière le niveau qui prouve que
   la thèse est fausse — l'autre côté du bloc, le point bas du balayage. Un
   stop « à 20 pips » ou « à 1 % » n'a aucune raison d'être : le marché ne
   connaît pas ton pourcentage.
2. **Pas de setup sous R:R 1,5** après coûts. Un R:R de 1,2 annoncé devient
   0,9 une fois le spread et le slippage comptés.
3. **Tout setup expire.** Une zone non touchée dans les N bougies de son
   timeframe est morte : le contexte qui l'a créée n'existe plus.

---

## 2. CRT — Candle Range Theory

Le plus représenté dans le corpus.

**Le principe.** Une bougie de référence définit un range. Le prix va souvent
chercher la liquidité d'un côté (balayage des stops), puis repart vers
l'autre côté. Le balayage n'est pas la cassure : c'est un piège.

**Vocabulaire des captures :**
- `IRL` — Internal Range Liquidity : la liquidité à l'intérieur du range
- `ERL` — External Range Liquidity : celle au-delà, la cible
- Le balayage doit être **rejeté**, pas confirmé

**Règles mesurables :**

```
1. Définir la bougie de référence (dans le corpus : la bougie de 9h)
   -> haut_crt, bas_crt

2. BALAYAGE : une bougie suivante dépasse haut_crt (ou bas_crt)
   MAIS clôture à l'intérieur du range
   -> c'est la condition qui distingue le piège de la vraie cassure

3. DÉPLACEMENT : la bougie suivante clôture dans le sens opposé
   au balayage, avec un corps >= 1,3 x le corps moyen des 20 dernières

4. ENTRÉE : sur la 3e bougie, au retour dans le range
   ou au retest du FVG créé par le déplacement

5. SL : au-delà de l'extrême du balayage, + 0,2 ATR de marge
6. TP1 : le côté opposé du range (ERL)
7. EXPIRATION : 3 bougies du timeframe
```

**Piège de conception :** ce pattern ressemble beaucoup, visuellement, à une
vraie cassure qui échoue. Sans la condition de clôture *à l'intérieur* du
range à l'étape 2, tu détectes les deux — et tu perds sur toutes les vraies
cassures. Cette condition est le cœur du pattern.

---

## 3. IFVG — Inversion Fair Value Gap

**Le principe.** Un FVG qui change de rôle. Un FVG haussier qui servait de
support devient résistance une fois que le prix a **clôturé** en dessous.
C'est une confirmation de changement de contrôle, souvent alignée avec un MSS.

```
1. Détecter un FVG (tu as déjà fair_value_gaps() dans structure.py)
2. INVERSION : une bougie CLÔTURE de l'autre côté du FVG
   -> une mèche qui traverse ne compte pas. Seule la clôture compte.
3. ENTRÉE : au retest du FVG inversé, désormais dans son nouveau rôle
4. SL : de l'autre côté du FVG, + 0,2 ATR
5. TP1 : le prochain déséquilibre ou le prochain pivot dans le sens du trade
6. EXPIRATION : 10 bougies après l'inversion
```

**Bon point :** `structure.py` détecte déjà les FVG. L'IFVG n'est qu'une
machine à états au-dessus — trois états : `actif` → `traversé` → `inversé`.
C'est peu de code pour une famille de setups entièrement nouvelle.

---

## 4. Volume Profile — POC, VAH, VAL

**Le principe.** Répartir le volume par niveau de prix, pas par temps. Les
niveaux à fort volume sont acceptés par le marché (support/résistance) ; ceux
à faible volume sont traversés vite.

| Terme | Définition | Usage |
|---|---|---|
| POC | niveau au volume maximal | aimant à prix, cible naturelle |
| VAH / VAL | bornes des 70 % de volume central | limites de la zone d'équilibre |
| HVN | nœud à fort volume | le prix ralentit, bon pour un TP |
| LVN | nœud à faible volume | le prix accélère, mauvais pour un TP |

**Calcul (aucune donnée tick nécessaire) :**

```python
def profil_volume(bars, n_niveaux=50):
    """Volume par niveau de prix, réparti sur le range de chaque bougie.

    Approximation assumée : on répartit le volume de chaque bougie
    uniformément sur son range. Le vrai profil demande des ticks. Sur du
    H1 et au-dessus, l'écart est faible et n'a jamais changé un POC de
    niveau dans nos essais. Sur du M5, ne pas s'y fier.
    """
    # -> {"poc": float, "vah": float, "val": float,
    #     "hvn": [float], "lvn": [float]}
```

**Setup principal — retest du POC :**
```
1. Le prix s'éloigne du POC de plus de 1,5 ATR
2. Il revient le tester
3. Rejet : une bougie clôture dans le sens du retour
4. ENTRÉE au rejet, SL derrière le POC + 0,3 ATR
5. TP1 : le bord de la zone de valeur (VAH ou VAL) dans le sens du trade
6. NE JAMAIS placer un TP dans un LVN — le prix y passe sans s'arrêter,
   et l'ordre ne se remplit pas
```

Ce dernier point est la règle la plus directement utile du corpus : elle
n'améliore pas le taux de détection, elle améliore le **taux de remplissage**
des objectifs.

---

## 5. ORB — Opening Range Breakout

La seule stratégie du corpus décrite avec des paramètres complets.

```
1. RANGE : les 15 premières minutes de la session de New York
   -> haut_orb, bas_orb
2. CASSURE : clôture au-delà d'un des deux bords
3. CONFIRMATION exigée (l'une ou l'autre) :
     - le prix est du bon côté du VWAP
     - cassure de structure dans le même sens
4. ENTRÉE : au retest du bord cassé (pas à la cassure elle-même)
5. SL : le côté opposé du range
6. TP1 : 1 x la hauteur du range, TP2 : 2 x
7. FENÊTRE : uniquement dans la première heure de la session
```

**Deux détails qui changent tout, et qui sont dans les captures :**
- L'entrée se fait **au retest**, pas à la cassure. Entrer sur la cassure,
  c'est acheter le haut du mouvement et se faire piéger par les faux départs.
- La **fenêtre horaire** est une condition, pas une préférence. Hors de la
  première heure, le range d'ouverture ne veut plus rien dire.

**VWAP à ajouter** (tu ne l'as pas dans `indicators.py`) :
```python
def vwap(bars, depuis_ouverture_session=True):
    """Prix moyen pondéré par le volume, remis à zéro à chaque session."""
```

---

## 6. Sessions — Asie, Londres, New York

Présent dans presque toutes les captures, et jamais paramétré dans ton code.

| Session | UTC | Comportement typique |
|---|---|---|
| Asie | 00:00 – 08:00 | range étroit, construit la liquidité |
| Londres | 08:00 – 16:00 | expansion, balaye souvent le range asiatique |
| New York | 13:00 – 21:00 | volume maximal, les grands mouvements |
| Chevauchement | 13:00 – 16:00 | le plus volatil de la journée |

**Le range asiatique sert de référence** : ses bornes sont les premières
cibles de liquidité de la session de Londres.

À ajouter dans un module `sessions.py` :
```python
def range_asiatique(bars) -> dict      # haut, bas, largeur en ATR
def session_active(ts) -> str          # "asie" | "londres" | "ny" | "chevauchement"
def balayage_asiatique(bars) -> dict   # le range a-t-il été balayé, de quel côté
```

⚠️ **Ces horaires ne valent que pour le forex et les métaux.** Le crypto cote
en continu : aucune session n'y a de sens, et appliquer ces filtres à BTC
produirait des règles arbitraires. Le module doit refuser de répondre pour un
instrument crypto plutôt que d'inventer une session.

---

## 7. Ordre d'implémentation

| # | Quoi | Pourquoi d'abord |
|---|---|---|
| 1 | `profil_volume()` + tests | aucune dépendance, réutilisable partout |
| 2 | `vwap()` + `sessions.py` | briques dont plusieurs stratégies dépendent |
| 3 | IFVG | s'appuie sur `fair_value_gaps()` déjà écrit — le moins cher |
| 4 | ORB | paramètres les plus clairs, donc le plus facile à backtester |
| 5 | CRT | le plus prometteur, le plus délicat à coder correctement |
| 6 | **backtest des 4** | 🔴 **la seule étape qui a de la valeur** |

Les étapes 1 à 5 produisent des candidats. L'étape 6 dit lesquels servent.
Sans elle, tu as juste quatre nouvelles façons de perdre de l'argent avec
conviction.

---

## 8. Ce que le corpus ne contient pas — et qui manque

En 130 captures, **aucune** ne montre :

- un taux de réussite mesuré sur un échantillon annoncé
- une courbe de drawdown
- le coût du spread ou du slippage
- ce qui arrive quand le setup échoue

C'est cohérent : ces comptes vendent des formations et de l'affiliation prop
firm, pas des résultats. Le contenu pédagogique est réel et les concepts
existent vraiment chez les professionnels — mais **la partie qui coûte de
l'argent quand elle manque est systématiquement absente**.

C'est exactement ce que ton `backtest-protocol` doit fournir. Le corpus donne
le *quoi*. Seul ton backtest donnera le *est-ce que ça marche chez moi*.
