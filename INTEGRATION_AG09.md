# Brancher AG-09 Constellation et AG-10 Miroir dans le site

> À donner à Claude Code avec `SYSTEME.md`. Cette note dit **exactement** où
> se branchent les deux nouveaux agents dans le code existant.
> Périmètre : analyse et affichage uniquement. Aucun ordre.

---

## 1. Ce qui existe déjà

| Fichier | Rôle | Ne pas casser |
|---|---|---|
| `constellation_agent.py` | `Constellation` (AG-09) + `Miroir` (AG-10) | ✅ testé, 20 tests verts |
| `tests/test_constellation.py` | les 20 tests | à garder verts |
| `verif.py` | contrôle automatique | à lancer après chaque changement |
| `gold_agent/tableau.py` | `collecter()` (l.398) → `agents_live()` (l.634) | c'est là que ça se branche |

`constellation_agent.py` ne fait **aucun appel réseau** : on lui injecte un
`DataFrame` de prix. C'est délibéré et il faut le garder ainsi — c'est ce qui
rend les 20 tests possibles sans internet.

---

## 2. ⚠️ Le piège à éviter absolument

La constellation a besoin de **~36 actifs × 3 ans de bougies quotidiennes**.

- **Ne l'appelle jamais depuis le rendu de la page.** Le téléchargement prend
  10 à 25 secondes : la page se figerait à chaque rafraîchissement.
- **N'utilise pas Twelve Data pour ça.** 36 actifs brûleraient le quota de
  800 requêtes/jour en une seule passe. `yfinance` est gratuit, sans clé, et
  n'a pas de quota exploitable.
- Les corrélations bougent sur des **semaines**, pas sur des secondes.
  Un recalcul toutes les **6 heures** est largement suffisant.

**Donc : calcul en tâche de fond, cache sur disque, la page lit le cache.**

---

## 3. Étape 1 — la source de données

Créer `gold_agent/constellation_source.py` :

```python
"""Prix quotidiens pour la constellation. Cache disque, recalcul 6 h.

Volontairement separe de datasource.py : Twelve Data est limite a
800 requetes/jour et sert au temps reel sur XAU/USD. Ici il faut 36 actifs
d'historique quotidien, ce que yfinance fournit gratuitement et sans cle.
"""
```

Ce module doit :

1. exposer `prix(force=False) -> pd.DataFrame` (colonnes = tickers)
2. mettre en cache dans `~/.constellation_prix.parquet` (ou `.csv.gz`)
3. **retourner le cache immédiatement** si sa date est < 6 h
4. si le cache est périmé : lancer le téléchargement dans un **thread**, et
   retourner l'ancien cache en attendant. La page ne bloque jamais.
5. si `yfinance` est absent ou le réseau coupé : retourner le dernier cache
   avec un drapeau `perime=True`. Jamais d'exception qui remonte à la page.
6. au tout premier lancement (aucun cache) : retourner `None`, et les cartes
   AG-09/AG-10 s'affichent en `INITIALISATION`.

L'univers des 36 tickers est déjà dans `constellation_agent.NOMS`.

---

## 4. Étape 2 — brancher dans `collecter()`

Dans `gold_agent/tableau.py`, fonction `collecter()` (ligne 398), ajouter un
bloc qui suit **exactement** le motif des autres sources (try/except large,
chrono, jamais d'exception qui remonte) :

```python
# --- constellation (AG-09/AG-10) ---------------------------------------
t0 = time.perf_counter()
paquet["constellation"] = None
try:
    from . import constellation_source
    from constellation_agent import Constellation, Miroir, biais_provisoire

    px = constellation_source.prix()
    if px is not None and "GC=F" in px.columns:
        ag = Constellation(px)
        biais = biais_provisoire(px)
        mi = Miroir(ag)
        g = ag.groupes("GC=F")

        # Le sens teste est celui du consensus courant, pas une hypothese.
        sens = "achat" if paquet["consensus"]["pct_haussier"] >= 50 else "vente"
        score = mi.evaluer("GC=F", sens, biais)

        paquet["constellation"] = {
            "sens_teste": sens,
            "satellites": [vars(m) for m in g["satellites"]],
            "miroirs": [vars(m) for m in g["miroirs"]],
            "n_decouples": len(g["decouples"]),
            "clusters": ag.clusters("GC=F"),
            "score": vars(score),
            "biais": biais,
            "ruptures": ag.ruptures(),
            "perime": getattr(px, "attrs", {}).get("perime", False),
        }
        ag.sauver()
except Exception as e:
    _evt("constellation", f"indisponible : {e}", "warn")
paquet["chrono"]["constellation"] = (time.perf_counter() - t0) * 1000
```

**Points non négociables :**

- le `try/except` est large **exprès** : une constellation indisponible ne
  doit jamais empêcher le reste du tableau de s'afficher
- `sens` vient du consensus réel, pas d'une hypothèse en dur
- `vars(m)` fonctionne parce que `Membre` et `ScoreIntermarche` sont des
  dataclasses — la sérialisation JSON est directe

---

## 5. Étape 3 — les deux cartes d'agent

Dans `agents_live()` (ligne 634), après AG-05 Minières & Flux, ajouter deux
cartes au **format exact** des autres (`code`, `nom`, `role`, `coul`,
`statut`, `activites`, `conviction`, `metriques`, `charge`) :

```python
c = d.get("constellation") or {}
sat, mir = c.get("satellites", []), c.get("miroirs", [])

# ---- AG-09 Constellation ----
if c:
    forts = [m for m in sat + mir if m["poids"] >= 0.60]
    trans = [m for m in sat + mir if m["tendance"].startswith("TRANSITION")]
    lignes = [f"{len(sat)} satellites · {len(mir)} miroirs · "
              f"{c['n_decouples']} découplés",
              "confirmations solides : " +
              (", ".join(f"{m['ticker']} {m['poids']:.2f}" for m in forts[:3])
               or "aucune")]
    if trans:
        lignes.append(f"{len(trans)} corrélations en transition de régime")
    for r in c.get("ruptures", [])[:2]:
        lignes.append(f"RUPTURE {r['actif']} : {r['avant']:+.2f} → {r['apres']:+.2f}")
    conviction = round(min(1.0, sum(m["poids"] for m in forts) / 2.0) * 100)
    statut = "PERIME" if c.get("perime") else "STREAMING"
else:
    lignes = ["cache en cours de construction"]
    conviction, statut = 0, "INITIALISATION"

agents.append({"code": "AG-09", "nom": "Constellation",
               "role": "Corrélations — satellites · miroirs · clusters",
               "coul": "#a371f7", "statut": statut, "activites": lignes,
               "conviction": conviction,
               "metriques": f"{len(c.get('clusters', []))} clusters · "
                            f"fenêtres 30/90/250 j · recalcul 6 h",
               "charge": charge("constellation")})

# ---- AG-10 Miroir ----
s = c.get("score") or {}
if s:
    lignes = [f"sens testé : {c['sens_teste']} · score {s['score']:+.2f}",
              f"base {s['base']:.2f}" + ("" if s["fiable"] else " — TROP MINCE"),
              f"{len(s['confirment'])} confirment · "
              f"{len(s['contredisent'])} contredisent"]
    if s["bloque"]:
        lignes.append("SIGNAL BLOQUÉ — " + s["motif"][:60])
    elif s["motif"]:
        lignes.append(s["motif"][:70])
    conviction = round((s["score"] + 1) / 2 * 100) if s["fiable"] else 50
    statut = "BLOCAGE" if s["bloque"] else ("ACTIVE" if s["fiable"] else "VEILLE")
else:
    lignes = ["en attente de la constellation"]
    conviction, statut = 50, "INITIALISATION"

agents.append({"code": "AG-10", "nom": "Miroir",
               "role": "Confirmation croisée intermarché",
               "coul": "#f778ba", "statut": statut, "activites": lignes,
               "conviction": conviction,
               "metriques": f"×{s.get('facteur_confiance', 1.0):.2f} sur la confiance",
               "charge": charge("constellation")})
```

**La `conviction` d'AG-10 est fixée à 50 quand la base est trop mince**, pas à
0 ni à 100. Une information insuffisante n'est ni un avis positif ni un avis
négatif — afficher autre chose que le neutre serait mentir sur l'écran.

---

## 6. Étape 4 — appliquer le facteur au signal

C'est ici que l'agent sert vraiment à quelque chose. Dans le calcul de la
fiabilité d'un setup, après le calcul actuel :

```python
c = paquet.get("constellation") or {}
s = c.get("score") or {}
if s and c.get("sens_teste") == setup["setup"].lower():
    if s["bloque"]:
        setup["suspendu"] = True
        setup["raison_suspension"] = "contradiction intermarché : " + s["motif"]
    else:
        setup["confiance"] = round(
            min(1.0, setup["confiance"] * s["facteur_confiance"]), 3)
        setup["intermarche"] = {
            "score": s["score"], "base": s["base"], "fiable": s["fiable"]}
```

⚠️ **Ce bloc modifie la logique de signal.** `SYSTEME.md` le classe en
« demander avant » : montre le diff à Mushine et attends sa validation avant
de l'appliquer.

Le champ `intermarche` doit être conservé dans le journal, sinon on ne pourra
jamais mesurer si le Miroir améliore réellement les résultats — et c'est la
seule question qui compte à terme.

---

## 7. Étape 5 — l'onglet Constellation

Un onglet à côté des existants, qui affiche pour l'or :

- 🟢 **Satellites** : ticker, corr, poids, biais actuel, ✅ confirme / ❌ contredit
- 🔴 **Miroirs** : idem
- ⚪ **Découplés** : le nombre seulement, la liste sur clic
- Les **clusters** encadrés visuellement, avec la mention
  *« ce groupe compte pour une seule voix »* — c'est ce qui rend le score
  compréhensible quand 13 lignes produisent une base de 2,28
- Le **verdict** : score, base, fiable ou non, qui confirme, qui contredit
- Les **ruptures de régime**, s'il y en a — en haut, en rouge

Une corrélation marquée `TRANSITION ^` s'affiche avec sa flèche : c'est un
changement de régime en cours, pas du bruit.

---

## 8. Ordre de travail

| # | Étape | Vérification |
|---|---|---|
| 1 | `constellation_source.py` + son test (cache périmé, cache absent, réseau coupé) | `verif.py` vert |
| 2 | bloc dans `collecter()` | `paquet["constellation"]` non vide, page toujours < 2 s |
| 3 | cartes AG-09 / AG-10 | les deux cartes s'affichent avec des chiffres réels |
| 4 | onglet Constellation | lisible, clusters visibles |
| 5 | **application du facteur** | ⚠️ montrer le diff et attendre validation |

Après **chaque** étape : `python3 verif.py`. Ne pas passer à la suivante sur
du rouge.

---

## 9. Ce qu'il ne faut pas faire

- ❌ Appeler `yfinance` depuis le rendu de la page
- ❌ Passer la constellation par Twelve Data
- ❌ Écrire une relation de corrélation en dur (« EUR/USD est un miroir de
  l'or ») — **les données disent +0,18, c'est-à-dire découplé**
- ❌ Laisser une exception de la constellation faire tomber le tableau
- ❌ Afficher une conviction de 0 ou 100 quand la base est trop mince
- ❌ Modifier `constellation_agent.py` sans relancer les 20 tests

---

## 10. Rappel : `biais_provisoire()` est temporaire

Le biais de chaque membre est aujourd'hui calculé avec deux moyennes mobiles
auto-calibrées. Ça suffit pour afficher quelque chose de vrai, pas pour
décider.

À terme il doit venir de **AG-02 Structure** — `structure.py`, `ict.py`,
`patterns.py`, `regime.py` appliqués à chaque membre. Cela suppose la Phase 0
(rendre `features/` symbole-agnostique), puisqu'il faudra faire tourner ces
modules sur GDX, l'argent et le DXY, et pas seulement sur XAU/USD.

Ne pas supprimer `biais_provisoire()` avant que le remplacement soit en place
et testé.
