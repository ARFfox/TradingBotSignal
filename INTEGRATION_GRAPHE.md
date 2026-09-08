# Le réseau des agents — note pour Claude Code

> À lire avec `SYSTEME.md`. Deux fichiers sont fournis, testés :
> `graphe_agents.py` (le modèle) et `graphe.html` (le rendu).

---

## 1. Ce que ce graphe doit être — et ce qu'il ne doit pas être

Un schéma où « l'agent A est relié à l'agent B » est une **décoration** : il
est identique quand le système va bien et quand il va mal. Il est joli une
fois et on ne le regarde plus jamais.

Ici, **tout ce qui est visible est mesuré à l'instant du rendu** :

| Élément visuel | Ce qu'il mesure |
|---|---|
| taille du nœud | conviction réelle de l'agent |
| halo pulsant | l'agent est actif |
| nœud gris pointillé | **l'agent est muet** — il ne répond plus |
| épaisseur du lien | force de la relation mesurée |
| couleur du lien | confirme (vert) · contredit (jaune) · **blocage (rouge animé)** · corrélation (bleu) |
| flèche | avance mesurée d'un marché sur un autre |

Le test de réussite : **on doit repérer un désaccord ou un agent mort en une
seconde**, sans lire un seul chiffre. Si le graphe ne fait pas ça, il ne sert
à rien et il vaut mieux ne pas le mettre.

---

## 2. Le modèle — `graphe_agents.py`

```python
from graphe_agents import construire

g = construire(
    cartes=paquet["agents"],                        # les cartes du panneau
    intermarches=(paquet.get("marches") or {}).get("graphe"),
    miroir=(paquet.get("constellation") or {}).get("score"),
    avocat=paquet.get("avocat"),                    # optionnel
)
paquet["graphe"] = g.json()
```

**Les quatre arguments sont optionnels.** Un graphe partiel vaut mieux qu'une
exception : un agent sans carte s'affiche en gris « muet », ce qui est
exactement l'information qu'on veut voir. Ne jamais entourer cet appel d'une
logique qui masque un agent absent.

Les 16 nœuds et leurs liens d'écoute sont dans le dictionnaire `AGENTS` :
c'est une **donnée**. Ajouter un agent = ajouter une entrée, aucun code.

Les couches ordonnent la lecture, de gauche à droite :

```
perception → marché → relation → critique → décision → chef → sortie
Vigie        Forex     Constellation  Avocat   Stratège  Superviseur  Notification
Structure    Crypto    Intermarchés                                   Toi
Traceur      Matières  Miroir
Flux         Actions
```

---

## 3. La route API

```python
if self.path == "/api/graphe":
    self.envoyer_json((paquet_courant() or {}).get("graphe") or {"noeuds": [], "liens": []})
```

Le front interroge toutes les 15 s — même cadence que le reste du panneau.
**Ne recalcule rien dans cette route** : elle lit le paquet déjà construit.

---

## 4. Le rendu — `graphe.html`

Autonome : canvas, aucune bibliothèque externe, ~250 lignes. À insérer tel
quel dans la page, ou à servir comme fragment.

Deux points à ne pas casser :

- **Le biais de couche dans la simulation.** Les nœuds sont rappelés vers la
  colonne de leur couche. Sans ce rappel, un graphe force-directed mélange
  tout et devient illisible — c'est ce qui arrive à la plupart des captures
  d'écran qui circulent : elles sont impressionnantes et ne se lisent pas.
- **Les liens porteurs d'information tirent plus fort que les liens de flux.**
  Résultat : deux agents en désaccord se rapprochent visuellement et sautent
  aux yeux.

Pour brancher le clic sur un nœud :

```js
window.ouvrirAgent = (code) => { /* ouvrir la page de l'agent */ };
```

Pour injecter des données sans passer par le fetch (tests) :
`window.grapheCharger({noeuds, liens})`.

---

## 5. Ordre de travail

| # | Étape | Vérification |
|---|---|---|
| 1 | copier `graphe_agents.py` à la racine | `python3 graphe_agents.py` affiche la démo |
| 2 | `paquet["graphe"]` dans `collecter()` | 16 nœuds, liens non vides |
| 3 | route `/api/graphe` | renvoie du JSON en < 50 ms |
| 4 | insérer `graphe.html` | le graphe s'anime, les infobulles marchent |
| 5 | onglet ou section dédiée | remplace la vue 3D actuelle, ou coexiste |

`python3 verif.py` après chaque étape.

---

## 6. Ce qu'il ne faut pas faire

- ❌ Dessiner un lien qui n'est pas mesuré, « pour faire joli »
- ❌ Masquer les agents muets — c'est précisément ce qu'on veut voir
- ❌ Recalculer quoi que ce soit dans `/api/graphe`
- ❌ Retirer le biais de couche (le graphe devient illisible)
- ❌ Mettre une flèche quand `jours == 0` (il n'y a pas d'avance mesurée)

---

## 7. La suite : les skills qui manquent encore

Par ordre de valeur réelle, pas de difficulté :

**1. `journal-intermarche`** 🔴 — enregistrer, à chaque signal, le champ
`intermarche` (score, base, fiable) **et** le résultat du trade. Sans ça, il
sera impossible de répondre à la seule question qui compte dans trois mois :
*est-ce que le Miroir améliore vraiment les résultats, ou est-ce qu'il bloque
au hasard ?* Tout le reste est secondaire tant que cette mesure n'existe pas.

**2. `walkforward-protocol`** 🔴 — le protocole de validation. Aucune
stratégie n'émet sans l'avoir passé. Toujours pas écrit.

**3. `regime-detector`** 🟠 — la corrélation comme détecteur de changement de
régime. `Constellation.ruptures()` produit déjà les données ; il manque la
règle : quand l'or/VIX repasse positif, l'or redevient valeur refuge et les
stratégies calibrées sur le régime actuel cessent de marcher.

**4. `agent-loop`** 🟠 — la boucle permanente avec heartbeat et reprise sur
crash. C'est ce qui rendra les agents réellement « toujours en ligne ».

**5. `brier-calibration`** 🟠 — les poids des agents calculés sur leur
performance passée, par instrument et par timeframe. Aujourd'hui `debate.py`
utilise encore des poids choisis à la main : c'est le maillon faible de tout
le système.

**6. `notification-router`** 🟡 — une seule source de vérité pour la pastille
de l'interface et la notification téléphone.

---

## 8. Une mise au point nécessaire

Les captures qui circulent — « 526 594 $ en 61 jours », « 570 665 $ »,
« Sharpe 4.91 », « 88 % de réussite » — sont des **publicités**. Un Sharpe de
4,9 dépasse ce que réalisent les meilleurs fonds quantitatifs au monde avec
des équipes de dizaines de docteurs et des données à la microseconde. Ces
chiffres ne sont pas vérifiables, et les comptes qui les publient vendent
des formations ou des programmes d'affiliation de prop firms.

Ce qui est réutilisable dans ces captures, c'est **l'idée visuelle** — et
c'est pour ça que ce graphe est construit. Ce qui ne l'est pas, c'est le
niveau de performance affiché : s'en servir comme point de comparaison
conduit à prendre trop de risque pour rattraper un chiffre qui n'existe pas.

Le vrai repère est ailleurs, et il est dans ton projet : `config.py` coupe
l'émission sur M15 parce que le backtest mesure +0,06R. **C'est un vrai
chiffre, mesuré, sur tes données.** Un système honnête qui sait ce qu'il ne
sait pas vaut infiniment plus qu'un tableau de bord spectaculaire.
