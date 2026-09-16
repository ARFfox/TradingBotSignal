# APPLIQUER — tout ce que Claude Code doit faire, dans l'ordre

> **Claude Code : ce fichier se suffit à lui-même.** Il contient les
> 9 modifications à appliquer au projet, dans l'ordre, avec le code exact et
> le critère qui dit que c'est fini. Applique-les **une par une**, et lance
> `python3 verif.py` après chacune.
>
> Les modules cités (`garde_fous.py`, `pips.py`, `avocats.py`…) sont déjà à
> la racine du projet, testés — **ne les réécris pas**. Ton travail est de
> les BRANCHER dans `gold_agent/` et `web.py`.
>
> État de départ : **222 tests verts**. Si `verif.py` passe au rouge après
> une étape, corrige avant de passer à la suivante.

---

## Règles non négociables

Elles priment sur tout le reste de ce fichier. Si une consigne ci-dessous
semble les contredire, ce sont elles qui gagnent.

1. **On n'optimise jamais le taux de réussite.** On pilote le R total. Le
   taux est un résultat qu'on affiche, jamais une cible qu'on poursuit.
2. **Un signal jamais entré ne compte dans aucun taux et dans aucun pip.**
3. **Sous 20 signaux résolus**, afficher « échantillon insuffisant » à la
   place du pourcentage — pas à côté.
4. **Stop minimum 1 ATR**, jamais assoupli.
5. **Un paramètre à la fois**, jamais deux ensemble.
6. **Le défaut d'une position est « neutre », jamais « pour ».**
7. **Ne jamais désactiver un contrôle de `verif.py`** — le signaler et
   proposer une règle plus précise.
8. **Tout changement automatique est journalisé et réversible.**
9. **Une mesure passe toujours devant une opinion.** Si la conviction dit
   83 % et le walk-forward dit −0,44R sur 23 trades, c'est le −0,44R qui
   prend la place principale.
10. **Aucun chiffre n'est global.** Taux, R, pips : toujours rattachés à un
    instrument, et si possible à un timeframe.

---

## Ce que les rapports disent DÉJÀ — lis ça avant de coder

`rapport_superviseur.md` et `rapport_sous_ensembles.md` ont tourné le
16/09/2026 à 16:13 sur **651 signaux / 405 résolus / −143,0R**. Quatre
résultats changent les priorités.

### 1. L'audit des stops ne fonctionne pas — et c'est LE blocage

```
317 stops touchés · 0 % par stop trop serré
  indetermine        314   ← 99 %
  direction_fausse     2
  stop_trop_serre      1
```

`indetermine` à 99 % ne veut pas dire « les stops vont bien ». Ça veut dire
que **le module ne peut pas répondre** : il lui manque l'`atr` à l'émission
et les bougies après le SL. C'est exactement ce que l'**étape 1** installe.

> Tant que cette colonne est à 314, tu ne sais pas si tu perds parce que tes
> stops sont trop serrés ou parce que ton analyse est fausse. Ce sont deux
> pannes opposées, avec deux corrections opposées. **Aucune autre étape ne
> vaut la peine avant celle-là.**

### 2. Les trois agents mesurés ne servent à rien

```
AG-01  n=403  ×0.10  discr. +0.35   vote quasiment toujours pareil
AG-05  n=403  ×0.10  discr. −0.35   vote quasiment toujours pareil
AG-10  n=403  ×0.10  discr. −0.35   vote quasiment toujours pareil
```

Trois agents qui votent pareil 403 fois sur 403 ne votent pas : ils
récitent. Un agent dont on connaît la réponse d'avance n'apporte aucune
information, quelle que soit la qualité de son raisonnement.

**C'est exactement ce que le débat AG-16/AG-18 corrige** (étape 6) : sur un
signal sans relief, les deux avocats se taisent. Un agent qui se tait est
un agent qui parle quand il a quelque chose à dire.

Note aussi les deux `discr. −0.35` : AG-05 et AG-10 sont des
**contre-indicateurs**. Ne les supprime pas — un agent qui a tort de façon
fiable porte de l'information.

### 3. Le verdict sur le seuil est tombé

```
AUCUN seuil ne rend le système positif — le problème n'est pas
le filtrage, c'est la stratégie elle-même
```

C'est l'issue que j'avais annoncée comme probable, et c'est la réponse la
plus utile qu'on pouvait obtenir : elle est arrivée sur **405 trades
mesurés** au lieu de six mois de doute. Elle dit que le travail est dans
les **conditions d'entrée**, pas dans le tri.

### 4. Une seule chose a survécu

```
vente + marché crypto    n=97   35 %   IC [21 %–53 %]   +0,01R   hors : 42 %
                                                                  PROMETTEUR
```

Sur 26 sous-ensembles testés avec correction des tests multiples, **un seul**
dépasse le hasard (31,5 % à ce R:R) — et il tient hors échantillon à 42 %,
c'est-à-dire mieux que dans l'échantillon d'apprentissage. C'est le signe le
plus encourageant du rapport.

Mais lis la borne basse : **21 %**. Sur 97 signaux, « 35 % » signifie
« quelque part entre 21 % et 53 % ». Une espérance de **+0,01R** est à peine
au-dessus de zéro.

> **Ce que ça vaut, honnêtement :** c'est une piste, pas une stratégie. Ne
> construis pas un système « vente crypto uniquement » sur 97 signaux. Note
> ce couple, laisse-le accumuler des résolus, et refais tourner le rapport.
> S'il tient encore à 200 signaux, alors c'est un edge.

---

## Étape 1 — Les 3 champs du journal 🔴 BLOQUANT

Sans eux, tout le reste est affamé : le superviseur ne peut rien apprendre
d'un « SL » qui ne dit pas pourquoi.

**Fichier : `gold_agent/journal.py`**

Ajouter à chaque signal enregistré :

```python
"emis": bool,                  # ce signal a-t-il été AFFICHÉ/NOTIFIÉ ?
"atr": float,                  # ATR du timeframe À L'ÉMISSION
"spread": float,               # spread constaté à l'émission
"extreme_favorable": float,    # rempli par garde_fous.suivre()
"tp_atteint_apres_sl": bool,   # rempli par garde_fous.suivre()
"r_realise": float | None,
"intermarche": dict,           # {"score":…, "base":…, "fiable":…} (AG-10)
"debat": dict,                 # {"verdict":…, "score":…, "contre":[…], "pour":[…]}
```

Puis remplacer la résolution actuelle par :

```python
from garde_fous import suivre

r = suivre(signal, bougies_depuis_emission)
signal.update({
    "statut": r.statut,
    "r_realise": r.r_realise,
    "extreme_favorable": r.extreme_favorable,
    "tp_atteint_apres_sl": r.tp_atteint_apres_sl,
})
```

> ⚠️ `suivre()` fait deux choix pessimistes **voulus** : une bougie qui
> touche SL et TP compte comme SL (l'OHLC ne donne pas l'ordre), et le scan
> continue après le SL pour remplir `tp_atteint_apres_sl`. Ne les
> « corrige » pas : un backtest optimiste est pire qu'un backtest absent.

**Fini quand :** un nouveau signal résolu porte les 8 champs, et
`superviseur_apprenant.auditer_sl()` renvoie autre chose qu'`indetermine`.

---

## Étape 2 — Le stop minimum 🔴 BLOQUANT

Première cause des 276 SL. Cas réel : cuivre M5, entrée 6.50 / SL 6.49 =
**0,29 ATR**, soit 2 à 5 fois le spread. Le prix le touche en respirant.

**Fichier : `gold_agent/strategy.py`**, au moment de l'émission :

```python
from garde_fous import valider_signal

v = valider_signal(entree, sl, tp, sens, atr, spread)
if not v["ok"]:
    _evt("emission", f"refusé {instrument} {tf} : {v['motif']}")
    return None
sl = v["sl"]        # stop élargi si nécessaire
```

> ⚠️ **L'ordre compte** : on élargit le stop D'ABORD, on vérifie le R:R
> ENSUITE. Sur le cuivre, le R:R tombe de 3,00 à **0,86** après
> élargissement — le setup ne tenait que par un stop irréaliste. Il doit
> être refusé, et c'est le comportement recherché.

**Fini quand :** aucun signal émis n'a un stop sous 1 ATR, et le nombre de
signaux émis **chute nettement**. La chute est le résultat, pas un bug.

### 2.1 — Le second constat de la capture : la porte est grande ouverte

Ligne réelle du 16/09/2026, en tête de l'historique :

```
XAU/USD  M5  vente  entrée 4348.58  SL 4353.83  TP 4337.83  NOTE 5 %  → SL
```

**Un signal noté 5 % a été affiché et notifié.** Une note de 5 % veut dire
que le système lui-même n'y croit pas — et il l'a quand même montré. Le
seuil d'émission ne filtre rien.

Tant que ça reste vrai, mesurer, pondérer et calibrer ne sert à rien : le
journal se remplit de signaux que personne n'aurait dû voir, et ils
écrasent le peu de signal utile.

### 2.2 — 🛑 NE FILTRE PAS SUR LA NOTE. Elle est à l'envers.

**Ceci ANNULE une consigne antérieure de ce fichier.** J'avais proposé un
seuil provisoire `note >= 0,35`. Le rapport du superviseur, lancé depuis,
montre qu'il **filtrerait dans le mauvais sens**. La mesure, sur 405
résolus :

| note annoncée | n | taux RÉEL | R moyen |
|---|---:|---:|---:|
| 0 – 20 % | 37 | **22 %** | −0,44R |
| 20 – 40 % | 224 | **25 %** | −0,27R |
| 40 – 60 % | 144 | **17 %** | −0,45R |

**Plus le système est confiant, moins il a raison.** La bande 40–60 % est la
PIRE des trois. Un seuil à 0,35 garderait justement cette bande et couperait
une partie de la bande 20–40 %, qui est la meilleure.

L'écart 25 % → 17 % donne `z = 1,88` : suggestif, pas concluant à lui seul.
Mais on ne filtre pas sur un indicateur dont le signe n'est même pas établi.

> 🛑 **Aucun filtrage sur la note tant qu'elle n'est pas reconstruite.**
> Filtrer sur un indicateur inversé revient à sélectionner activement les
> perdants — c'est pire que de ne rien filtrer.

**À faire à la place**, dans cet ordre : l'**étape 2** (stop minimum) et
l'**étape 3** (anti-contradiction), qui ne dépendent d'aucune note.
`seuil_optimal()` a déjà répondu : *aucun seuil ne rend le système positif*.
Le filtrage n'est pas la solution ; c'est la note elle-même qui est à
refaire.

> **Pourquoi je laisse mon erreur écrite ici au lieu de l'effacer :** ce
> fichier sera relu. L'idée « filtrons sur la confiance » est naturelle et
> reviendra toute seule. Il faut qu'elle reste barrée, avec le chiffre qui
> la barre.

---

## Étape 3 — Anti-contradiction 🔴 BLOQUANT

Cas réel : `12:17 GDX M15 VENTE` et `12:17 GDX M5 ACHAT`. Quoi qu'il
arrive, l'un des deux perd.

**Fichier : `gold_agent/strategy.py`**, avant l'émission du lot :

```python
from garde_fous import filtrer_lot

gardes, refuses = filtrer_lot(candidats)
for r in refuses:
    _evt("emission", f"refusé {r['instrument']} {r['tf']} : {r['motif']}")
```

**Fini quand :** plus aucun couple achat/vente sur le même instrument, et
chaque refus est visible avec son motif. Tu dois pouvoir savoir **pourquoi**
un signal n'est pas sorti.

---

## Étape 4 — Le rapport du superviseur 🔴 BLOQUANT

**Nouveau fichier : `taches/rapport_quotidien.py`**

```python
from pathlib import Path
from superviseur_apprenant import rapport, charger_journal
from chercheur_sous_ensembles import rapport as rapport_sous_ensembles
from pips import bilan, rapport as rapport_pips

j = charger_journal(JOURNAL)
Path("rapport_superviseur.md").write_text(rapport(j), encoding="utf-8")
Path("rapport_sous_ensembles.md").write_text(rapport_sous_ensembles(j), encoding="utf-8")
Path("rapport_pips.md").write_text(rapport_pips(bilan(j)), encoding="utf-8")
```

À lancer toutes les 24 h, ou dès **20 nouveaux résolus**.

> ⚠️ Le rapport annoncera peut-être qu'**aucun seuil ne rend le système
> positif**. C'est l'issue probable et c'est la réponse la plus utile : elle
> dit que le travail est dans les conditions d'entrée, pas dans le filtrage.
> Ne masque pas ce verdict.

**Fini quand :** les trois rapports existent et se régénèrent seuls.

---

## Étape 5 — Remplacer le Profit Factor par les pips 🟠

**C'est la demande directe : afficher les pips gagnés, et des pips négatifs
quand il y a plus de pertes.**

La tuile visée est la 4ᵉ de l'onglet **Signaux validés**, celle qui affiche
aujourd'hui `0.00 / profit factor`.

### 5.0 — ⚠️ D'ABORD : ce 0.00 est un BUG, pas un résultat

Capture du 16/09/2026 : `−105.83R · 22.5 % · 80 TP / 276 SL · 356 résolus`.
Le profit factor affiché est `0.00`. **Il devrait valoir 0.62.**

```
pertes cumulées = 276 SL × 1R           = 276.00 R
gains cumulés   = −105.83 + 276.00      = 170.17 R
profit factor   = 170.17 / 276.00       =   0.617
```

Un PF de 0,00 signifierait **aucun gain du tout**, ce qui est contredit par
les 80 TP affichés juste à côté. Les deux chiffres viennent de la même page
et ne peuvent pas être vrais en même temps.

**Cause la plus probable :** le PF somme `r_realise`, qui vaut `None` ou `0`
pour tous les signaux — alors que le « R cumulé » est calculé autrement (à
partir du `rr` et du statut) et, lui, donne le bon résultat. Il y a donc
**deux chemins de calcul et un seul fonctionne**.

> 🔴 **Ne remplace pas la tuile avant d'avoir trouvé ça.** Si `r_realise`
> n'est pas alimenté, les pips seront faux exactement de la même façon — et
> cette fois personne ne le remarquera, parce qu'un total de pips n'a pas de
> valeur « impossible » évidente comme un PF à 0,00.

**Fini quand :** en console, `sum(s["r_realise"] for s in resolus if s["r_realise"] and s["r_realise"] > 0)` renvoie ≈ **+170**, pas 0. C'est le
test qui débloque tout le reste de cette étape.

### 5.1 — Le calcul

**Fichier : `web.py`**, dans la route qui sert l'historique :

```python
from pips import bilan, resume_court, rapport as rapport_pips

# ⚠️ On calcule sur les signaux DÉJÀ FILTRÉS par l'interface
# (marché, instrument, timeframe), jamais sur le journal entier.
b = bilan(signaux_filtres)

entete = {
    "pips_net":     round(b.net),          # NÉGATIF s'il y a plus de pertes
    "pips_gagnes":  round(b.gagnes),
    "pips_perdus":  round(b.perdus),
    "unite":        b.lignes[0].unite if len(b.fiables) == 1 else "pips/points",
    "melange":      b.melange,             # True = plusieurs instruments
    "r_total":      round(b.r_total, 1),
    "n_resolus":    b.n_resolus,
    "n_tp":         b.n_tp,
    "taux":         b.taux,
    "resume":       resume_court(b),       # ligne prête à afficher
}
```

### 5.2 — L'affichage

La tuile `0.00 / profit factor` devient, en gardant exactement la même
place et la même typographie que les trois autres :

```
AVANT                           APRÈS
┌──────────────┐                ┌──────────────────────┐
│    0.00      │                │   − 12 480           │
│ profit factor│      ───►      │   pips nets          │
└──────────────┘                │ +8 600 · −21 080     │
                                └──────────────────────┘
                                  rouge si négatif
```

Les trois autres tuiles ne bougent pas : `R cumulé`, `taux de validés`,
`résolus / émis`. Le R reste la mesure qui compte — les pips sont le
chiffre qu'on lit, le R est celui qui décide.

Règles d'affichage, toutes obligatoires :

| Règle | Pourquoi |
|---|---|
| Le **signe** est toujours visible, jamais une valeur absolue | « 1 240 pips » et « −1 240 pips » sont des situations opposées |
| **Rouge** si `pips_net < 0`, **vert** sinon | c'est l'information principale |
| Le **R total** reste affiché à côté | seul agrégat comparable entre marchés |
| Si `melange = true`, afficher le marqueur **≠** avec une infobulle | voir ci-dessous |
| Sous 20 résolus : « échantillon insuffisant » **à la place** du taux | règle 3 |

Texte de l'infobulle **≠** :

> Ce total additionne des instruments différents. 1 pip d'EUR/USD vaut
> environ 10 $, 1 pip d'or environ 1 $ : +500 pips sur l'or et −500 sur
> EUR/USD ne s'annulent pas. Filtre sur un seul instrument pour un chiffre
> exact. Le R, lui, est comparable partout.

> ⚠️ **Ne supprime pas ce marqueur pour faire plus propre.** Un total de
> pips tous marchés confondus ne correspond à aucune somme d'argent. Il
> montre le sens, pas le montant.

### 5.3 — Les instruments manquants

`pips.py` exclut du total tout instrument absent de sa table `TAILLE_PIP`,
et le signale. Sur la démo, 4 signaux mal convertis produisaient à eux seuls
96 % du total. Si le rapport signale des instruments inconnus, **ajoute-les
dans `TAILLE_PIP`** — ne contourne pas l'exclusion.

**Fini quand :** l'historique affiche des pips signés, rouges quand c'est
négatif, avec le R à côté ; et le rapport `rapport_pips.md` ne signale plus
aucun instrument inconnu.

---

## Étape 6 — Brancher le débat AG-16 / AG-18 🟠

**Fichier : `gold_agent/strategy.py`**, juste avant d'émettre :

```python
from avocats import Contexte, debat, calibrer

ctx = Contexte(
    atr=atr, spread=spread,
    score_intermarche=inter["score"], base_intermarche=inter["base"],
    base_fiable=inter["fiable"],
    regime_marche=agent_marche.regime,
    instrument_leader=(agent_marche.leader == instrument),
    confluence_tf=n_timeframes_alignes,
    news_dans_h=heures_avant_news,
    esperance_combo=esp, n_combo=n_combo,
    seuil_note_mesure=seuil_mesure,
)
v = debat(signal, ctx, poids_arguments)

if v.bloque:
    _evt("emission", f"BLOQUÉ par le débat : {v.contre[0].texte}")
    return None

note = min(1.0, note * v.facteur)          # ⚠️ jamais au-dessus de 100 %
signal["debat"] = {
    "verdict": v.verdict, "score": v.score,
    "contre": [{"code": a.code, "texte": a.texte, "mesure": a.mesure} for a in v.contre],
    "pour":   [{"code": a.code, "texte": a.texte, "mesure": a.mesure} for a in v.pour],
}
```

La calibration, dans `taches/rapport_quotidien.py` :

```python
from avocats import calibrer, rapport_calibration

paires = [(s, contexte_stocke(s)) for s in j if s.resolu]
poids_arguments = {k: v.poids for k, v in calibrer(paires).items()}
Path("rapport_avocats.md").write_text(rapport_calibration(calibrer(paires)))
```

> ⚠️ Un argument marqué **« à retourner »** prédit l'inverse de ce qu'il
> affirme. Ce n'est pas un bug : c'est un contre-indicateur, donc de
> l'information. Affiche-le, ne le supprime pas.

**Fini quand :** chaque signal porte son `debat`, les signaux `BLOQUÉ` ne
sortent plus, et `rapport_avocats.md` donne un poids mesuré par argument.

---

## Étape 7 — Le graphe avec les positions 🟠

**Fichiers : `web.py` + `graphe.html`**

```python
from graphe_agents import construire, depuis_verdict

avocat, defense, positions = depuis_verdict(v)     # v = Verdict de l'étape 6
for c in cartes:
    if c["code"] in positions:
        c["position"] = positions[c["code"]]
        # chaque autre agent renseigne "pour" | "contre" | "neutre"

g = construire(cartes, intermarches, miroir, avocat, defense)
return g.json()        # GET /api/graphe
```

`graphe.html` s'intègre tel quel : anneau **vert = pour**, **rouge =
contre**, **gris = neutre**, et le décompte `5 pour · 3 contre · 6 neutre`
en bas.

Trois règles d'affichage :

- **Le défaut est « neutre », jamais « pour ».** Un silence compté comme un
  accord fabrique une unanimité qui n'existe pas.
- **Ne déduis jamais la position de la conviction.** Une conviction de 90 %
  sur « le marché est baissier » est CONTRE un achat et POUR une vente.
  Confondre les deux afficherait l'inverse de la vérité.
- **Un agent muet n'a pas d'anneau.** Un mort ne vote pas.

**Fini quand :** le graphe change d'un signal à l'autre. S'il ne change
jamais, les agents ne votent pas — ils récitent, et c'est un bug.

---

## Étape 8 — Le site : tout est par instrument 🟠

**C'est la demande, et elle est plus qu'une question d'affichage.** Un taux
global de 21,7 % vaut pour l'or, pour le Bitcoin et pour EUR/USD à la fois —
donc pour aucun des trois. Cliquer sur l'or doit montrer l'or.

Le module `vue_instrument.py` fait tous les calculs. **Ne les refais pas
dans `web.py`** : deux pages qui calculent le même taux finissent toujours
par afficher deux chiffres différents.

### 8.0 — 🛑 Trois bugs visibles sur les captures, à corriger d'abord

**Bug 1 — deux bandeaux se contredisent.** Sur la même page, en cliquant
BTC/USD :

```
bandeau A : « L'analyse 5 timeframes reste celle de XAU/USD
              (l'instrument du compte) »
bandeau B : « BTC/USD — analyse seulement. Chaque timeframe affiche
              son verdict walk-forward réel »
```

Et la carte H4 montre bien des prix BTC (entrée 75 545,67). Donc le
bandeau A est un **texte périmé** qui ment. Supprime-le. Un bandeau faux est
pire qu'aucun bandeau : il apprend à ne plus lire les bandeaux.

**Bug 2 — on ne voit pas quel timeframe porte le signal.** La rangée
`H4 · H1 · M30 · M15 · M5` a une pastille minuscule et tronquée sur H4.
Correctif au §8.3.

**Bug 3 — une conviction de 83 % sur un setup mesuré à −0,44R.** 🔴

```
H4 · STRUCTURE · conviction 83 %
walk-forward REFUSÉ · 23 trades · R moyen −0.439
```

C'est la **même inversion** que la calibration de la note (§2.2) : plus le
système est confiant, moins il a raison. Les deux chiffres sont côte à côte
sur la même carte et se contredisent.

> **Règle d'affichage :** quand le walk-forward d'un couple est REFUSÉ, la
> conviction **ne s'affiche pas en vert**. Elle se grise, et le verdict
> mesuré passe devant. Une conviction est une opinion ; un R moyen sur
> 23 trades est une mesure. **La mesure gagne toujours la place principale.**

**Bug 4 — le meilleur chiffre du projet est affiché en rouge.** 🟢

Sur la carte H4 de XAU/USD, un badge **rouge** annonce :

```
mesuré · 3 ans, stop 1,5 ATR : +1,12R
```

**+1,12R est un résultat positif.** Mesuré sur trois ans, avec un stop à
1,5 ATR. C'est le chiffre le plus encourageant de tout le système, et il est
peint de la couleur des pertes — donc personne ne le lit.

Il confirme aussi directement l'étape 2 : **quand le stop est placé
honnêtement, la stratégie devient positive.** Le problème n'a jamais été
l'analyse, c'est la géométrie.

> Règle : le badge prend la couleur du **signe du R mesuré**. Positif = vert,
> négatif = rouge. Jamais l'inverse, jamais une couleur fixe.

### 8.1 — Registre d'instruments

**Nouveau fichier : `core/instruments.py`** — une seule source de vérité :

```python
INSTRUMENTS = {
    "XAU/USD": {"nom": "Or", "marche": "matieres",
                "tv": "OANDA:XAUUSD", "decimales": 2},
    "BTC/USD": {"nom": "Bitcoin", "marche": "crypto",
                "tv": "BINANCE:BTCUSDT", "decimales": 2},
    # … un par instrument
}
MARCHES = ["matieres", "forex", "crypto", "actions"]
```

Boutons, listes, graphe, pips et `TAILLE_PIP` lisent ce fichier.
**Aucune liste d'instruments codée en dur ailleurs.**

### 8.2 — La fiche instrument

**Fichier : `web.py`**, route `/api/instrument/<nom>` :

```python
from vue_instrument import fiche, toutes_les_fiches, badges_par_marche

f = fiche(journal, instrument, signaux_actifs)

return {
    "instrument": f.instrument,
    "marche":     f.marche,
    "badge":      f.badge,              # signaux EN COURS
    "tf_signal":  f.tf_avec_signal,     # ["H4", "M15"]
    "sous_hasard": f.sous_le_hasard,
    "global": {
        "texte":     f.global_.texte_taux,   # ⚠️ utilise CE texte
        "taux":      f.global_.taux,         # None = insuffisant
        "n":         f.global_.n_resolus,
        "r_total":   f.global_.r_total,
        "pips_net":  f.global_.pips_net,
        "hasard":    f.global_.hasard,
        "n_attente": f.global_.n_attente,
        "n_expire":  f.global_.n_expire,
    },
    "timeframes": [
        {"tf": tf, "n": c.n_resolus, "taux": c.taux, "ic": c.ic,
         "r_moyen": c.r_moyen, "pips": c.pips_net, "verdict": c.verdict,
         "signal": tf in f.tf_avec_signal, "texte": c.texte_taux}
        for tf, c in f.timeframes.items()
    ],
    "historique": f.signaux[:200],      # DÉJÀ filtré sur cet instrument
}
```

> 🔴 **`taux` vaut `None` quand il y a moins de 20 résolus.** Dans ce cas la
> page écrit **« échantillon insuffisant (3/20) »** À LA PLACE du
> pourcentage — jamais à côté, jamais en petit, jamais un `0 %`.
>
> Ce n'est pas de la prudence décorative. 405 résolus ÷ 25 instruments ÷
> 5 timeframes = **3,2 signaux par case**. Un « 67 % » sur 3 trades est un
> tirage à pile ou face affiché en gras, et il fait prendre des décisions.
>
> Le champ `texte` contient déjà la bonne phrase dans les deux cas. Affiche-le
> tel quel et le problème ne peut pas arriver.

### 8.3 — Les 5 timeframes, tous visibles

Les cinq boutons `H4 · H1 · M30 · M15 · M5` sont **toujours affichés**, même
sans données. Un timeframe absent du tableau se lit « pas de signal », alors
qu'il veut dire « pas de données » — ce n'est pas la même chose.

Sur chaque bouton :

| Élément | Règle |
|---|---|
| **Pastille rouge** | uniquement si `signal = true` — lisible, pas tronquée |
| **Verdict** sous le nom | `AUTORISÉ` vert · `COUPÉ` rouge · `OBSERVATION` jaune · `INSUFFISANT` gris |
| **Effectif** | `n=48` en petit, toujours |
| Bouton **grisé** si `COUPÉ` | il reste cliquable — on doit pouvoir regarder ce qu'on a coupé |

Le titre de la page affiche l'instrument **et** les timeframes en signal :

```
BTC/USD · Bitcoin                    🔴 signal sur H4
```

L'analyse des 5 timeframes est **celle de l'instrument cliqué**, jamais
celle de l'or. C'est le bug 1.

### 8.4 — L'historique, filtré par instrument

Le tableau `SIGNAUX VALIDÉS` ne montre que l'instrument sélectionné —
`f.signaux` est déjà filtré, il suffit de ne pas le refiltrer.

| Colonne | Règle |
|---|---|
| Ne compter que les signaux dont l'entrée a été touchée | règle 2 |
| `TP` → **validé** · `SL` → **non validé** | demandé explicitement |
| `expire` → **exclu du taux**, affiché dans une ligne à part | on doit voir qu'on annonce des entrées jamais atteintes |
| Taux | le champ `texte` du §8.2, tel quel |
| **Pips nets** | signés, rouges si négatifs (étape 5) |
| Cause du SL | `stop_trop_serre` / `direction_fausse` (étape 1) |

Un sélecteur de timeframe filtre encore : `BTC/USD → H4` montre les résolus
de BTC sur H4 uniquement, avec son propre effectif.

### 8.5 — Les badges qui remontent

```python
fiches = toutes_les_fiches(journal, signaux_actifs)
badges = badges_par_marche(fiches)        # {"crypto": 9, "matieres": 3}
```

Le badge d'un marché est la somme de ses instruments. **Il compte les
signaux EN COURS, jamais l'historique** — un badge qui compte des trades
finis ne se vide jamais, et on arrête de le regarder.

Au clic sur un marché : la liste de ses instruments, ceux qui portent un
signal en premier (`toutes_les_fiches` les trie déjà).

### 8.6 — Cases d'agents

Des cases d'agents reliées à une case **Superviseur**. Chaque case : nom,
conviction, statut, et **sa position** (pour / contre / neutre) avec les
couleurs de l'étape 7. Le graphe et les cases lisent la même source.

**Fini quand :** cliquer sur l'or montre l'historique de l'or, son taux, ses
5 timeframes avec leur verdict ; cliquer sur EUR/USD change tout ; et aucune
case sous 20 résolus n'affiche de pourcentage.

### 8.7 — La mise en page et le thème clair

**Référence visuelle : `maquette.html`** à la racine du projet. Elle est
autonome, elle s'ouvre dans un navigateur, et **son CSS est la source des
valeurs** — reprends les variables telles quelles plutôt que d'en inventer.

#### Le thème clair

Le fond passe en blanc. ⚠️ **Ce n'est pas « le thème sombre avec le fond
changé »** — c'est l'erreur classique, et elle donne du gris clair illisible
sur du blanc. Toutes les encres et tous les statuts ont été recalculés :

```css
:root{
  --fond:#ffffff;  --surface:#fafaf9;  --surface-2:#f4f4f2;
  --bord:#e4e3df;  --bord-fort:#cdccc7;
  --encre:#17171a;  --encre-2:#52514e;  --encre-3:#76746f;

  --perte:#b3261e;        /* TEXTE   — 6,5:1 sur blanc */
  --perte-marque:#d03b3b; /* MARQUES — barres, points */
  --gain:#006300;         /* TEXTE   — 7,5:1 */
  --gain-marque:#0ca30c;
  --attention:#8a5a00;    /* TEXTE   — 5,9:1 */
  --accent:#1c5cab;       /* TEXTE   — 6,6:1 */
}
```

> **Deux verts et deux rouges, ce n'est pas une erreur.** `#0ca30c` sur blanc
> ne donne que 3,35:1 : correct pour une barre, **insuffisant pour du texte**
> (4,5:1 exigé). Le vert vif va sur les marques, le vert foncé sur les
> chiffres. Le thème sombre garde ses propres valeurs et reste disponible par
> le bouton — le clair est le défaut.

#### 🔴 Le signe porte le sens, jamais la couleur seule

Le rouge et le vert du tableau sont à **ΔE 4,1 en deutéranopie** (mesuré) :
pour environ **8 % des hommes**, ce sont deux gris identiques. Un tableau de
trading qui n'encode le résultat que par la couleur est illisible pour eux.

Donc, partout et sans exception :

| Élément | Forme obligatoire |
|---|---|
| R | `+1.66` / `−1.00` — **le signe, toujours** |
| Pips | `+1 344` / `−525` |
| Résultat | `✓ validé (TP)` / `✗ non validé (SL)` — **icône + mot** |
| Variation de prix | `▲ 0.13 %` / `▼ 0.42 %` |
| Verdict d'un TF | le mot écrit (`coupé`, `autorisé`), pas juste la teinte |

#### La mise en page

```
┌──────────────────────────────────────────────────────────────┐
│ XAU/USD · Or spot   4 348.58 ▼0.42%      🔴1 signal sur M5   │
├──────────────────────────────────────────────────────────────┤
│ [Matières 3] [Forex 4] [Crypto 9] [Actions]                  │
│ [XAU/USD] [BTC/USD] [EUR/USD] [ETH/USD] …  ← défile          │
├──────────────────────────────────────────────────────────────┤
│  −19.0 R    │ taux ▓▓▓▓▓░░░│░░ 18 %   │ −6 086  │  39 / 61   │
│  R cumulé   │      équilibre 30 % ↑    │  pips   │ résolus    │
├──────────────────────────────────────────────────────────────┤
│ [TOUS] [H4] [H1] [M30] [M15] [M5🔴]   ← PLEINE LARGEUR       │
├───────────────────────┬──────────────────────────────────────┤
│  SIGNAL               │  GRAPHIQUE TradingView               │
│  conviction · badge   │  ┌────────────────────┐              │
│  garde-fou            │  │ analyse en surcouche│             │
│  entrée / SL / TP     │  └────────────────────┘              │
│  RSI · ATR · ext.     │                                      │
├───────────────────────┴──────────────────────────────────────┤
│ [Signaux validés 8] [Historique complet 39] [Risque]         │
│  filtres TF · 5 lignes visibles, le reste défile             │
└──────────────────────────────────────────────────────────────┘
```

Quatre changements par rapport à l'actuel :

**Les timeframes prennent toute la largeur.** `grid-template-columns:
repeat(6, 1fr)`. Chaque bouton porte son nom, son **verdict** et son
**effectif** — `M5 · coupé · n=20`. Un bouton `coupé` est atténué
(`opacity:.62`) mais reste cliquable : on doit pouvoir regarder ce qu'on a
coupé.

**Signal à gauche (400 px fixe), graphique à droite (le reste).** L'analyse
s'affiche **en surcouche sur le graphique**, pas en dessous. Sous 1100 px, la
grille passe à une colonne.

**Le bandeau de stats passe de 5 tuiles à 4.** « 21,7 % » et « 28,7 %
équilibre à atteindre » étaient deux nombres qui ne veulent rien dire
séparément — l'un n'a de sens que comparé à l'autre. Ils deviennent **une
jauge** : la barre remplie est le taux mesuré, le trait vertical est
l'équilibre. L'écart se voit sans lire un chiffre.

> Et un seul **chiffre héros** par vue (38 px) : le **R cumulé**. C'est la
> mesure qui décide. Tout le reste est en 24 px.

**L'historique passe dans son propre onglet.** `Signaux validés` |
`Historique complet` | `Risque événementiel`. Le premier ne montre que les
résolus ; le second montre tout, y compris les jamais entrés.

#### Le défilement à 5 lignes

```css
.defile{
  max-height: 252px;          /* ≈ 5 lignes + l'en-tête */
  overflow-y: auto;
  overscroll-behavior: contain;   /* ⚠️ indispensable */
}
thead th{ position: sticky; top: 0; }   /* l'en-tête reste visible */
```

> `overscroll-behavior: contain` empêche le défilement de « sauter » à la page
> entière quand on arrive en bas du tableau. Sans lui, deux doigts sur le
> trackpad d'un Mac font partir la page au moment où on cherche la ligne
> suivante — c'est le défaut le plus pénible d'un tableau défilant, et il
> tient en une ligne de CSS.

**Fini quand :** le fond est blanc, les 6 boutons de timeframe occupent toute
la largeur, le graphique est à droite du signal, le tableau montre 5 lignes
puis défile sans emporter la page, et chaque chiffre coloré porte son signe.

---

## Étape 9 — Vérification finale

```bash
python3 verif.py              # doit afficher VERT
python3 -m pytest tests/ -q   # 222 passed
```

Puis les trois contrôles que seul un humain peut faire :

1. **Le nombre de signaux a-t-il chuté ?** Si non, l'étape 2 n'est pas
   vraiment branchée.
2. **Le graphe change-t-il d'un signal à l'autre ?** Si non, les positions
   ne sont pas renseignées.
3. **Y a-t-il encore des SL à `indetermine` ?** Si oui, l'étape 1 est
   incomplète.
4. **Un clic sur l'or, puis sur EUR/USD : tout change-t-il ?** Historique,
   taux, 5 timeframes, pips. Si un seul chiffre reste identique, il n'est
   pas filtré.
5. **Une case sous 20 résolus affiche-t-elle un pourcentage ?** Si oui,
   `texte_taux` n'est pas utilisé et la page recalcule dans son coin.

---

## Le chiffre à ne jamais perdre de vue

Dernière mesure, `rapport_superviseur.md` du 16/09/2026 à 16:13 :

```
651 émis · 405 résolus · 21,7 % · −143,0R · gain moyen +1,98R
```

```
hasard      = 1 / (1 + 2,17) = 31,5 %      ← et c'est aussi l'équilibre
le système  =                  21,7 %
écart       =                  −9,8 points
```

**Le système prédit moins bien qu'une pièce lancée.** Il n'a pas un edge
faible : il en a un négatif. La cause la plus probable n'est pas l'analyse
mais la géométrie — un stop dans le bruit détruit le R:R réel quelle que
soit la valeur affichée.

### Ce que coûte chaque jour d'attente

```
il y a quelques jours   548 émis · 288 résolus ·  −78,0R
capture du site         619 émis · 356 résolus · −105,8R
rapport de 16:13        651 émis · 405 résolus · −143,0R
                        ────────────────────────────────
                        +103 émis · +117 résolus · −65,0R
```

117 trades de plus, **−65R de plus** — soit **−0,56R par signal résolu**, et
la pente s'aggrave. Ce n'est pas un argument pour se presser sur
l'interface. C'est un argument pour faire les **étapes 1 et 2 d'abord** :
ce sont les seules qui arrêtent l'hémorragie.

> Si tu ne devais faire qu'une chose cette semaine : l'**étape 1**. Sans
> elle, les 314 `indetermine` restent, et personne — ni toi, ni moi, ni
> aucun agent — ne peut dire pourquoi 317 stops ont sauté.

Aucune interface, aucun avocat et aucun graphe ne répare ça. C'est la
géométrie des stops, et c'est l'**étape 2**. Fais-la en premier.

> Après les étapes 1 à 4, le nombre de signaux va chuter très fortement —
> peut-être de 619 à quelques dizaines. **C'est le résultat recherché.** Un
> système qui émet 619 signaux à 22 % ne souffre pas d'un manque de signaux.
> Il souffre d'un excès de signaux qu'il n'aurait pas dû montrer — la ligne
> notée **5 %** du §2.1 en est la preuve à l'écran.
