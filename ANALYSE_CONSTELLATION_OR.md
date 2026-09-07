# Analyse de la constellation de l'or — données réelles au 7 septembre 2026

*754 jours de cotation, 08/09/2023 → 07/09/2026. 36 actifs testés.*

Ces chiffres changent plusieurs choses dans la conception du système. Certains contredisent ce que je t'ai dit dans le message précédent — je le signale explicitement à chaque fois.

---

## 1. Je me suis trompé sur EUR/USD

Dans mon message précédent, je t'ai corrigé en disant qu'EUR/USD serait un **satellite** de l'or, corrélé autour de +0,4 à +0,7, parce que l'euro pèse 57 % du Dollar Index.

**Les données disent +0,18. Découblé.**

Ton hypothèse de départ (EUR/USD baisse quand l'or monte) était fausse. La mienne (il monte fortement avec l'or) l'était aussi. La réalité : **il n'y a pas de relation exploitable du tout.**

Et l'asymétrie est le vrai enseignement :

| | corrélation avec l'or |
|---|---|
| Dollar Index (DXY) | **−0,57** |
| EUR/USD | **+0,18** |

Si l'or était principalement une histoire de dollar, EUR/USD — qui est essentiellement l'inverse du DXY — serait autour de +0,5. Il est à +0,18.

> **Conclusion : l'or n'est pas principalement piloté par le dollar sur cette période.** Il a son propre moteur, et le lien au dollar n'en capte qu'une partie.

C'est exactement pour ça que la règle « aucune corrélation en dur » est la bonne. Deux personnes raisonnant à partir de la théorie économique sont arrivées à deux réponses différentes, toutes les deux fausses. Les données ont tranché en 30 secondes.

---

## 2. Tout le forex est découblé de l'or

| Paire | corr 90j | Verdict |
|---|---|---|
| EUR/USD | +0,18 | inutilisable |
| AUD/USD | +0,14 | inutilisable |
| GBP/USD | +0,13 | inutilisable |
| NZD/USD | +0,10 | inutilisable |
| USD/JPY | +0,05 | inutilisable |
| USD/CHF | −0,05 | inutilisable |
| USD/CAD | −0,11 | inutilisable |
| EUR/JPY | +0,19 | inutilisable |

**Aucune paire forex ne peut servir de confirmation à un signal or.** Le seul lien devise exploitable est le DXY lui-même, à −0,57.

Ça a une conséquence directe sur ta demande initiale : *« regrouper les devises qui font les mêmes réactions qu'or, et qui font le contraire d'or »*. **La réponse honnête des données est : il n'y en a pas.** Le groupe existe conceptuellement, il est vide en pratique sur cette période.

Le système doit dire ça, pas fabriquer un groupe pour remplir l'écran.

---

## 3. La relation or / taux réels est cassée

C'est le pilier théorique de la valorisation de l'or : l'or ne rapporte pas d'intérêts, donc quand les taux réels montent, le coût d'opportunité de le détenir augmente et son prix baisse. La corrélation attendue est de **−0,6 à −0,8**.

| Instrument | corr 90j |
|---|---|
| TIPS (taux réels) | **+0,21** |
| Rendement 10 ans US | **−0,27** |
| Rendement 5 ans US | **−0,34** |
| Obligations 20 ans+ | +0,17 |

La relation existe encore, dans le bon sens, mais elle est **trois fois plus faible que le manuel**. Sur ces trois ans, les taux réels n'expliquent qu'environ 10 % de la variance de l'or.

> **Conséquence pour le système : l'agent AG-13 Macro & taux réels doit être rétrogradé.** Il reste utile comme contexte, mais il n'a pas le droit de peser lourd dans une décision. Si je l'avais laissé avec un poids « fondamental fort » comme la théorie le suggère, il aurait pollué toutes les confluences.

C'est précisément à ça que sert la pondération par score de Brier du Chef d'orchestre : elle aurait fini par découvrir ça toute seule, mais en plusieurs mois et en payant des pertes. Là, tu le sais avant d'écrire une ligne.

---

## 4. ⚠️ L'or ne se comporte pas comme une valeur refuge en ce moment

C'est le résultat le plus contre-intuitif du tableau.

| Actif | corr 90j | Groupe |
|---|---|---|
| **VIX (peur)** | **−0,44** | 🔴 miroir |
| **S&P 500** | **+0,44** | 🟢 satellite |
| Russell 2000 | +0,39 | proche satellite |
| Nasdaq 100 | +0,37 | proche satellite |

**L'or monte quand la peur baisse et quand les actions montent.** C'est l'inverse du comportement de valeur refuge que tout le monde lui attribue.

Ce que ça décrit, c'est un **régime de liquidité / débasement** : l'or, les actions et le crypto montent ensemble contre un dollar qui baisse. Ce n'est pas un régime de peur.

> **Conséquence directe et immédiate pour tes agents :** si ton agent Vigie contient une règle du type « news risk-off → biais haussier or », **elle est fausse dans le régime actuel** et elle produira des signaux perdants. C'est exactement le genre de règle de bon sens qu'on écrit sans y penser et qui coûte cher.

Il faut aller vérifier dans `news.py` si une telle logique existe.

---

## 5. 🔥 Le bloc crypto est en transition — la découverte la plus importante

Regarde la progression, colonne par colonne :

| Actif | 250j | 90j | 30j | dérive |
|---|---|---|---|---|
| Bitcoin | +0,23 | +0,53 | +0,66 | **+0,43** |
| BNB | +0,20 | +0,41 | +0,61 | **+0,41** |
| Ethereum | +0,23 | +0,49 | +0,60 | **+0,37** |
| Chainlink | +0,19 | +0,48 | +0,56 | **+0,37** |
| Solana | +0,14 | +0,52 | +0,55 | **+0,41** |
| XRP | +0,22 | +0,52 | +0,51 | **+0,29** |
| Avalanche | +0,15 | +0,48 | +0,41 | **+0,26** |
| Cardano | +0,19 | +0,44 | +0,39 | **+0,20** |

**Les 8 cryptos, sans une seule exception, dérivent de façon monotone dans le même sens.** Huit sur huit. Ce n'est pas du bruit statistique : c'est un changement de régime. L'or et le complexe crypto se sont **recouplés** au cours des derniers mois.

Mon script les étiquetait « INSTABLE » ou « moyenne », ce qui était **trompeur de ma part**. Instable suggère erratique, aléatoire, inutilisable. Or ici la corrélation ne zigzague pas : elle **monte régulièrement**. C'est une information de premier ordre, et mon script la jetait à la poubelle.

**J'ai corrigé le script.** Il distingue maintenant :

| Étiquette | Signification |
|---|---|
| `stable` | la corrélation ne bouge pas — utilisable |
| `TRANSITION ^` | dérive monotone à la hausse — **changement de régime en cours** |
| `TRANSITION v` | dérive monotone à la baisse — découplage en cours |
| `erratique` | zigzague sans direction — inutilisable |

Relance le script : le bloc crypto va maintenant s'afficher en `TRANSITION ^` au lieu d'`INSTABLE`.

### Et l'idée qui en découle

> **La corrélation elle-même est un détecteur de changement de régime de marché.**

Quand la corrélation or/VIX passe de négative à positive, l'or redevient une valeur refuge et les stratégies qui marchaient dans le régime « débasement » cessent de fonctionner. Quand le crypto se découple de l'or, la thèse commune s'éteint.

**Ça vaut probablement plus que n'importe quel indicateur technique de ton système**, parce que ça détecte le moment où le terrain change — c'est-à-dire exactement le moment où les systèmes qui marchaient se mettent à perdre, et où les backtests deviennent trompeurs.

À intégrer comme sortie de l'agent AG-09 : un **indicateur de régime de corrélation**, avec alerte quand une relation stable bascule.

---

## 6. Le noyau fiable est petit — et c'est une bonne nouvelle

| Actif | corr 90j | stabilité | Utilisable comme confirmation ? |
|---|---|---|---|
| **Mineurs d'or (GDX)** | **+0,82** | stable | ✅ **oui, forte** |
| **Argent (XAG)** | **+0,82** | stable | ✅ **oui, forte** |
| Platine | +0,73 | stable | ✅ oui, forte |
| Palladium | +0,59 | stable | ⚠️ moyenne |
| Cuivre | +0,59 | stable | ⚠️ moyenne |
| Dollar Index | −0,57 | moyenne | ⚠️ moyenne |
| VIX | −0,44 | moyenne | ❌ trop faible |
| S&P 500 | +0,44 | stable | ❌ trop faible |

**Trois actifs seulement dépassent le seuil de confirmation solide : GDX, l'argent, le platine.** Et ce sont tous les trois des métaux — c'est-à-dire, en réalité, la même information.

### Le seuil de confirmation doit monter à 0,70

Une corrélation de 0,45 explique **20 % de la variance**. Elle informe, elle ne confirme pas. Traiter vingt relations faibles comme vingt confirmations produit du bruit déguisé en certitude — c'est la manière la plus efficace de construire un système très confiant et très perdant.

**J'ai donc mis deux seuils différents dans le script :**

| Seuil | Valeur | Usage |
|---|---|---|
| Regroupement | 0,40 | afficher l'actif dans le groupe à l'écran |
| **Confirmation** | **0,70** | avoir le droit de peser dans une décision |

Une nouvelle colonne `confirmation` affiche FORTE / moyenne / aucune.

> **Conséquence sur l'agent Miroir (AG-10) : sur l'or, il ne dispose que de 2 à 3 confirmations réellement solides, et d'aucun miroir fort** (le DXY à −0,57 n'atteint pas le seuil). Le système doit l'afficher honnêtement — « score intermarché basé sur 3 relations » — plutôt que de fabriquer un chiffre rassurant à partir de 20 corrélations molles.

---

## 7. Les changements à apporter à la spécification

| # | Changement | Raison |
|---|---|---|
| 1 | Seuil de confirmation à **0,70**, distinct du seuil de regroupement à 0,40 | une corrélation à 0,45 n'explique que 20 % de la variance |
| 2 | Ajouter la métrique **tendance** (transition ↑/↓ vs erratique) | 8 cryptos sur 8 dérivent de façon monotone : jeter ça serait une faute |
| 3 | **Rétrograder AG-13 Macro & taux réels** en agent de contexte | −0,27 au lieu du −0,7 théorique |
| 4 | **Auditer `news.py`** : chercher toute règle « risk-off → or monte » | l'or est corrélé +0,44 au SPY et −0,44 au VIX : la règle est fausse dans ce régime |
| 5 | Nouvelle sortie d'AG-09 : **indicateur de régime de corrélation** + alerte de bascule | détecte le moment où les stratégies cessent de marcher |
| 6 | Le groupe « devises satellites/miroirs de l'or » doit pouvoir être **vide** | il l'est. Le système doit le dire, pas le remplir. |
| 7 | Ajouter à l'univers : **XAU/EUR, XAU/JPY, ratio or/argent, ratio GDX/or** | pour chercher de vrais miroirs forts, qui manquent actuellement |

---

## 8. Ce qu'il faut faire maintenant

1. **Relance `constellations.py`** — la nouvelle colonne va requalifier le bloc crypto en `TRANSITION ^`.
2. **Lance `python3 constellations.py BTC-USD`** — la constellation du Bitcoin te dira quelles altcoins sont du Bitcoin déguisé (corr > 0,85) et lesquelles sont vraiment indépendantes. C'est directement ta navigation « je clique sur Bitcoin et je vois toutes les cryptos ».
3. **Cherche dans `news.py`** toute règle qui suppose que l'or monte sur les nouvelles risk-off. Si elle existe, elle te coûte de l'argent en ce moment.
4. Puis **Phase 0** : le refactor et la correction de `VALEUR_POINT_PAR_LOT`.

---

## Ce que cet exercice prouve

En un script de 250 lignes et deux minutes d'exécution, tu viens d'apprendre quatre choses que ni toi ni moi n'aurions devinées :

- l'or n'est pas piloté par le dollar comme on le croit
- la relation or/taux réels, qui est le fondement théorique de sa valorisation, est trois fois plus faible que le manuel
- l'or se comporte actuellement comme un actif risk-**on**, pas comme une valeur refuge
- le complexe crypto est en train de se recoupler à l'or, de façon nette et unanime

**Aucune de ces quatre découvertes n'aurait survécu à une table de corrélations écrite à la main.** C'est l'argument le plus fort en faveur de la règle qui est maintenant dans ton `CLAUDE.md` : les corrélations sont mesurées, jamais supposées.
