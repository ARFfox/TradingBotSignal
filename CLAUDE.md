# Règles du projet — non négociables

> Le manuel complet est **`SYSTEME.md`** (à lire en premier). Ce fichier
> résume ce qui ne se discute pas. Si une demande le contredit, signaler la
> contradiction avant d'agir.

## La boucle obligatoire

```
COMPRENDRE → ÉCRIRE (une chose à la fois) → python3 verif.py → CORRIGER → ANNONCER (seulement sur VERT)
```

- Jamais « c'est fait » sans avoir lancé `python3 verif.py` (VERT exigé).
- Jamais désactiver un test ou élargir un seuil pour faire passer du code.
- Après 3 tentatives infructueuses sur la même erreur : s'arrêter et exposer
  les options à Mushine.
- Édition de fichiers par script : UNE substitution = UNE écriture, avec
  OK/ÉCHEC par étape (un assert au milieu d'un script multi-remplacements a
  déjà annulé des lots entiers d'éditions).

## Périmètre

1. Le système **analyse et notifie**. Il ne passe AUCUN ordre. Aucun code
   d'exécution tant que Mushine ne le demande pas explicitement.
2. Le système ne se modifie jamais seul : le Superviseur **propose**, Mushine
   clique, l'action est tracée.

## Émission de signal

3. Aucune stratégie n'émet sans avoir passé `research/walkforward.py`
   (fenêtres glissantes, purge, coûts, ≥ 30 trades, ≥ 2 régimes, PF > 1,3).
   Un candidat n'est pas un signal.
4. Toute modification de la logique de signal (seuils, filtres, suspension,
   consensus) = **demander avant**.
5. Chaque signal journalisé conserve `intermarche` et `avis` : c'est ce qui
   permettra de mesurer si le Miroir et la calibration Brier servent.

## Corrélations

6. **Aucune relation de corrélation en dur** — tout est recalculé sur les
   données (constellation, 6 h). Une corrélation instable ne peut ni
   confirmer ni contredire ; des membres corrélés votent UNE fois (clusters).
7. On corrèle les **rendements**, jamais les prix ; calendrier aligné sur les
   jours de cotation du pivot.

## Calculs

8. La valeur du point, le tick, les décimales et la traduction de symboles
   viennent **toujours** de `gold_agent/instruments.py` (le registre unique).
   `point_par_lot = 0.0` = non vérifié → le sizing REFUSE.
9. Une décision utilise un poids continu, jamais une étiquette à seuil.
10. Une base d'information mince peut faire douter, jamais rassurer.
11. Tout backtest inclut les coûts (`cout_pts` or fixe, `cout_pct` ailleurs).
12. Les poids des agents sont **calculés** (Brier, `gold_agent/avis.py`),
    jamais choisis. Depuis le 14/09 ils s'appliquent AUTOMATIQUEMENT à la
    note du Superviseur (`gold_agent/decision.py`), avec le journal 90 j —
    plus de blocages : une probabilité affichée, composant par composant ;
    le téléphone ne reçoit que les notes ≥ SEUIL_NOTIFICATION.

## Données et code

13. Aucun accès direct à une API : `feeds/` (seau à jetons, backoff, cache
    dont la taille demandée fait partie du contrat) ou les modules existants.
14. Aucune clé API dans le code — `.env` uniquement, jamais commité.
15. Aucun fichier ne dépasse 500 lignes ; toute fonction de calcul arrive
    avec son test dans `tests/` (invariant métier, sans réseau).
16. `python3 -m pytest tests/ -q` doit rester vert (130+ tests).

## Faits mesurés à ne pas oublier

- L'or spot n'a **pas de volume** chez Twelve Data : profil/VWAP se replient
  en poids temporels et l'annoncent (`source_poids`).
- yfinance n'a pas de 4 h natif : jamais de H4 étiqueté depuis du 1 h.
- Tout le forex est découplé de l'or ; seuls argent/GDX/platine confirment
  fort ; le crypto s'est **recouplé** (mesuré, voir ANALYSE_CONSTELLATION_OR).
- Les avertissements `verif.py` sur `instruments.py` et ses tests sont des
  faux positifs par conception (le registre EST l'endroit du littéral) —
  affinage de la règle en attente de validation.

## Rappels d'exploitation

- Site : `python3 -m gold_agent.web` (port 8787, boucles permanentes
  incluses). Rapports quotidiens : `~/.gold_agent_rapports/`.
- Rapports d'edge : `python3 -m research.rapport_edge` et
  `python3 -m research.rapport_strategies` (relancer périodiquement).
- Décisions en attente de Mushine : « affine verif » (faux positifs du
  registre) · « câble la règle 3 » (grille → émission) — les poids Brier
  sont déjà appliqués à la note du Superviseur (14/09).
