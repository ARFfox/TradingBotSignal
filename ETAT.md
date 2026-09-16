# ÉTAT RÉEL DU SYSTÈME — tout ce dont on a parlé, et où c'en est

> **Pour APPLIQUER tout d'un coup, va dans `APPLIQUER.md`.** Ce document-ci
> répond à une autre question : **qu'est-ce qui existe vraiment ?**
> Pas ce qui est prévu, pas ce qui est spécifié — ce qui tourne et qui est
> testé. Mis à jour le 16/09/2026. `python3 verif.py` → **VERT, 193 tests**.

Trois états, et un seul compte :

| | signification |
|---|---|
| ✅ **FAIT** | le code existe, il tourne, il est testé |
| 📄 **ÉCRIT** | la spécification existe, **le code n'existe pas** |
| ⬜ **RIEN** | on en a parlé, il n'y a rien |

---

## 1. Les modules du cerveau

| Module | Rôle | État | Tests |
|---|---|---|---|
| `statistiques.py` | hasard · Wilson · Bonferroni · marge de bruit | ✅ | via 3 modules |
| `pips.py` | **pips gagnés/perdus** par instrument | ✅ | 21 |
| `garde_fous.py` | stop minimum · anti-contradiction · suivi des SL | ✅ | 25 |
| `superviseur_apprenant.py` | AG-00 — audit SL, calibration, poids, seuil | ✅ | 30 |
| `parametres_agents.py` | réglage automatique, walk-forward | ✅ | 16 |
| `chercheur_sous_ensembles.py` | où se cache un taux élevé | ✅ | 17 |
| `avocats.py` | **AG-16 + AG-18, le débat contradictoire** | ✅ | 25 |
| `constellation_agent.py` | AG-09 Constellation + AG-10 Miroir | ✅ | 20 |
| `agents_marches.py` | AG-11..15 marchés + intermarchés | ✅ | 22 |
| `constellations.py` | explorateur de corrélations (CLI) | ✅ | — |
| `graphe_agents.py` · `graphe.html` | réseau d'agents + positions | ✅ | 17 |
| `verif.py` | contrôle automatique du projet | ✅ | — |

---

## 2. Les agents

| Code | Nom | État | Où |
|---|---|---|---|
| AG-00 | Superviseur apprenant | ✅ | `superviseur_apprenant.py` |
| AG-01 | Vigie (news) | ✅ existant | ton projet |
| AG-02 | Structure | ✅ existant | ton projet |
| AG-03 | Stratège | ✅ existant | ton projet |
| AG-04 | Traceur | ✅ existant | ton projet |
| AG-05 | Minières & Flux | ✅ existant | ton projet |
| AG-09 | Constellation | ✅ | `constellation_agent.py` |
| AG-10 | Miroir | ✅ | `constellation_agent.py` |
| AG-11..14 | Forex · Crypto · Matières · Actions | ✅ | `agents_marches.py` |
| AG-15 | Intermarchés | ✅ | `agents_marches.py` |
| AG-16 | **Avocat du diable** | ✅ **nouveau** | `avocats.py` |
| AG-18 | **Avocat de la défense** | ✅ **nouveau** | `avocats.py` |
| AG-99 | Vérificateur | ✅ | `verif.py` |
| AG-06 · AG-07 | Probabilité · Opportunités | ⬜ **volontairement abandonnés** |
| AG-17 | Rattrapage | ⬜ | jamais construit |

> **Pourquoi AG-06 et AG-07 n'existeront pas.** Probabilité, Opportunités et
> Superviseur faisaient le même métier en trois morceaux : chacun notait le
> même signal et personne ne tranchait. Les trois sont fondus dans AG-00.
> Un agent de moins qui décide vaut mieux que trois qui votent la même chose.

---

## 3. Le débat contradictoire — ce qui vient d'être ajouté

C'est la pièce qui manquait et dont on avait parlé. Deux avocats plaident sur
**les mêmes faits mesurés**, et l'historique départage.

```
😈 AG-16  cherche les faits qui PRÉCÈDENT une perte
🛡️ AG-18  cherche les faits qui PRÉCÈDENT un gain
```

Trois règles câblées dans le code :

**Un avocat qui plaide toujours ne plaide pas.** Sur un signal propre et sans
relief, les deux se taisent — et c'est testé. Un agent dont la conclusion est
connue d'avance ne porte aucune information.

**Aucun argument n'est une opinion.** Chacun porte le chiffre qui le fonde.
Sur le cuivre réel :

```
😈 le stop est à l'intérieur du bruit du marché       → 0.29 ATR (minimum 1.0)
😈 le gain/risque ne couvre pas le taux de réussite   → R:R 0.86 (minimum 1.5)
                        — affiché 3.00, mais avec un stop irréaliste
😈 les actifs corrélés vont dans l'autre sens         → score −0.45
😈 ce couple CUIVRE×M5 perd depuis le début           → −0.38R sur 34 signaux
🛡️ (rien)
→ BLOQUÉ
```

La ligne qui compte est la deuxième. **La défense n'a pas le droit de plaider
un R:R obtenu avec un stop irréaliste.** Le cuivre affiche 3,00 ; recalculé
avec un stop honnête, il vaut 0,86. Sans cette règle, AG-18 s'appuyait sur ce
qu'AG-16 venait de démonter — et j'avais écrit exactement ce bug avant de le
voir dans ma propre sortie.

**Une base mince peut faire douter, jamais rassurer.** Quand l'information est
insuffisante, la défense ne peut pas pousser la conviction au-dessus de 1,0.
Le doute, lui, passe. L'asymétrie est volontaire.

### Les avocats apprennent

`calibrer()` mesure, pour chaque argument, le R moyen quand il est présent
contre le R moyen quand il est absent :

- argument qui discrimine → poids proportionnel à l'écart ;
- argument qui ne discrimine rien → **poids zéro**, il disparaît du débat ;
- argument qui prédit l'INVERSE → signalé **« à retourner »**, pas supprimé :
  un contre-indicateur porte de l'information.

Deux garde-fous : sous 25 observations le poids reste à 1,0 (on ne recalibre
pas un agent sur douze trades), et un écart doit dépasser le bruit mesuré
avant de compter — sinon le module donnerait du poids à un argument tiré à
pile ou face.

---

## 4. Le graphe — pour / contre / neutre

| Ce qu'on voit | Ce que ça mesure |
|---|---|
| taille du nœud | conviction réelle |
| **anneau vert** | cet agent est **POUR** le signal en cours |
| **anneau rouge** | il est **CONTRE** |
| **anneau gris** | il n'a rien trouvé à dire |
| nœud pointillé gris | agent muet — il ne répond plus |
| couleur du lien | confirme / contredit / bloque, **en ce moment** |
| flèche double | avance mesurée d'un marché sur un autre |
| bandeau bas | `5 pour · 3 contre · 6 neutre` |

Trois décisions à connaître :

**Le défaut est « neutre », jamais « pour ».** Compter un silence comme un
accord fabriquerait une unanimité qui n'existe pas.

**La position n'est jamais déduite de la conviction.** Une conviction de 90 %
sur « le marché est baissier » est CONTRE un achat et POUR une vente. Les
confondre afficherait l'inverse de la vérité — c'est testé.

**Le décompte du bas est à surveiller.** S'il ne bouge jamais d'un signal à
l'autre, les agents ne votent pas : ils récitent.

---

## 5. Ce qui est ÉCRIT mais PAS construit

C'est la partie honnête du document. Ces choses ont une spécification
complète et **aucune ligne de code**.

| Quoi | Spécification | Qui doit le faire |
|---|---|---|
| Les 3 champs du journal (`emis`, `atr`, `spread`…) | `APPLIQUER.md` §1 | Claude Code |
| Stop minimum branché à l'émission | `APPLIQUER.md` §2 | Claude Code |
| Anti-contradiction branché | `APPLIQUER.md` §3 | Claude Code |
| Rapport du superviseur automatique | `APPLIQUER.md` §4 | Claude Code |
| Boutons Forex/Crypto/Stocks/Matières | `APPLIQUER.md` §8.2 | Claude Code |
| Cascade de notifications marché→instrument | `APPLIQUER.md` §8.3 | Claude Code |
| Timeframes en **boutons** | `APPLIQUER.md` §8.2 | Claude Code |
| En-tête fluide + TradingView au clic | `APPLIQUER.md` §8.2 | Claude Code |
| Historique → **signaux validés** + taux + **pips** | `APPLIQUER.md` §5 et §8.4 | Claude Code |
| Cases d'agents reliées au superviseur | `APPLIQUER.md` §8.5 | Claude Code |
| Registre `core/instruments.py` | `APPLIQUER.md` §8.1 | Claude Code |
| CCXT dans `feeds/` | `SKILL_OUTILS_EXTERNES.md` §1 | Claude Code |
| VectorBT pour le balayage | `SKILL_OUTILS_EXTERNES.md` §2 | Claude Code |
| Stratégies CRT / IFVG / ORB | `SKILL_STRATEGIES.md` | **en dernier** |
| AG-17 Rattrapage | ⬜ rien | à décider |

**Pourquoi je ne les ai pas construites d'ici :** ces pièces touchent
`gold_agent/`, `web.py` et le journal, qui sont sur ta machine et que Claude
Code connaît. Ce que j'écris ici sont des modules autonomes, testables seuls,
qu'il branche. Un module que j'écris à l'aveugle sur ton arborescence casse
plus qu'il ne répare.

---

## 6. Les deux défauts trouvés dans mon propre code aujourd'hui

Je les note parce qu'ils se reproduiront ailleurs.

**Le réglage automatique laissait passer 20 % de bruit pur.** Il exigeait
que 4 découpes sur 4 confirment un gain. Mais 4 sur 4 arrivent par hasard
dans 6 % des cas, et le module essayait **9 valeurs** : une fois sur cinq,
l'une d'elles réussissait par chance. C'est précisément le sur-apprentissage
que ce module existe pour empêcher, et il passait par sa propre porte.
Corrigé : la marge exigée est maintenant corrigée du nombre de valeurs
essayées. Le bruit accepté est tombé de **20 % à 0,8 %**, et un vrai gain
reste accepté (+0,975R, 4/4 découpes).

**Un de mes tests réussissait ou échouait au hasard.** Il utilisait `hash()`
d'une chaîne, que Python randomise à chaque démarrage. Il passait 4 fois sur
5. Un test qui échoue 20 % du temps est pire qu'un test absent : il fait
chercher une panne qui n'existe pas. Réécrit avec `crc32`, et surtout
reformulé pour tester la bonne chose — **un taux de faux positifs sur 40
tirages**, pas un seul tirage. Aucun garde-fou ne rejette le bruit à 100 % ;
ce qu'on exige, c'est qu'il passe rarement, et ça ne se mesure pas sur un
échantillon de 1.

---

## 7. L'ordre à suivre

Rien de la section 5 ne vaut la peine avant les 4 étapes bloquantes de
`CHANTIER.md`. Le cerveau est maintenant complet ; il est nourri par un
journal qui ne dit pas **pourquoi** un stop a sauté.

```
maintenant        étapes 1 → 4 de CHANTIER.md        (Claude Code, ta machine)
puis              étape 5, le chercheur              (il tourne sur des données propres)
puis              le site                            (§5 de ce document)
en dernier        les nouvelles stratégies
```

**Le chiffre à ne pas perdre de vue :** à un R:R de 2,09, le hasard touche le
TP **32,4 %** du temps. Le système est à 23,6 %. Il n'a pas un edge faible —
il en a un **négatif**. Aucune sélection, aucun avocat et aucun graphe ne
répare ça : c'est la géométrie des stops, et c'est l'étape 2.
