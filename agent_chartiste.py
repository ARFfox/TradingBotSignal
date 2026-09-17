#!/usr/bin/env python3
"""
AG-20 CHARTISTE — l'agent qui lit les graphiques, sur les 5 timeframes.

    python3 agent_chartiste.py        # démonstration

Ce qu'il fait que `figures.py` ne fait pas
-------------------------------------------
`figures.py` détecte des figures sur UNE série. Cet agent est la couche
au-dessus, et il ajoute trois choses qui n'existaient nulle part :

1. **Les NIVEAUX** — supports, résistances, points pivots, plus haut et plus
   bas du jour, zones d'offre et de demande. Ils étaient sur tes planches et
   n'étaient dans aucun module.

2. **La lecture MULTI-TIMEFRAME** — ce que disent H4, H1, M30, M15 et M5
   ensemble, et surtout **où ils se contredisent**.

3. **Une carte d'agent** — il prend position sur le graphe comme les autres,
   et alimente le débat des avocats et AG-19 Directeur.

La distinction qui commande tout le module
-------------------------------------------
**Un NIVEAU décrit. Une FIGURE prédit.** Ce n'est pas la même chose, et les
deux n'ont pas le même poids par défaut.

  · « le prix a tourné quatre fois entre 4 316 et 4 322 » est un FAIT
    vérifiable sur l'historique. Poids **1,0**.
  · « ce triangle annonce une hausse » est une PRÉDICTION que la littérature
    dit majoritairement fausse. Poids **0,0** jusqu'à mesure.

C'est pour ça que les niveaux sont dans cet agent et pas les figures : ce
sont deux métiers, et confondre les deux est la façon la plus courante de se
tromper en analyse graphique.

Le piège du multi-timeframe
----------------------------
Un double sommet visible sur H4 ET sur H1 n'est **pas** deux confirmations :
H1 contient les mêmes bougies que H4, en plus fin. C'est UNE observation vue
deux fois. Les compter séparément fabrique une confluence qui n'existe pas —
exactement le défaut qui avait produit « 16 sur 16, score +1,00 ».

`accord_timeframes()` pondère donc par échelle décroissante et ne compte
jamais deux fois la même figure sur deux timeframes voisins.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from figures import TAUX_SUR_BRUIT, detecter, pivots

# --------------------------------------------------------------------------
TIMEFRAMES = ("H4", "H1", "M30", "M15", "M5")

# Une bougie H4 = 4 bougies H1 = 48 bougies M5. Un signal vu sur H4 porte
# donc plus d'information qu'un signal vu sur M5 — mais surtout, les deux
# ne sont PAS indépendants.
POIDS_TF = {"H4": 1.00, "H1": 0.75, "M30": 0.55, "M15": 0.40, "M5": 0.30}

TOL_NIVEAU = 0.0025      # 0,25 % — deux touches au même niveau
N_MIN_TOUCHES = 2        # un « niveau » à une seule touche est un point
FORCE_MAX_TOUCHES = 5    # au-delà, la force du niveau plafonne


@dataclass
class Niveau:
    """Un prix où le marché a effectivement tourné. DESCRIPTIF."""
    prix: float
    genre: str            # "support" | "resistance"
    touches: int
    derniere: int         # index de la dernière touche
    force: float          # 0..1 — nombre de touches, borné

    def distance(self, prix_actuel: float) -> float:
        return abs(prix_actuel - self.prix) / prix_actuel if prix_actuel else 0.0

    def __str__(self) -> str:
        return (f"{self.genre} {self.prix:.5g} · {self.touches} touche(s) "
                f"· force {self.force:.2f}")


@dataclass
class LectureTF:
    """Ce que dit UN timeframe."""
    tf: str
    figures: list = field(default_factory=list)
    niveaux: list = field(default_factory=list)
    tendance: str = "neutre"       # haussier | baissier | neutre — DESCRIPTIF
    pente_pct: float = 0.0
    position_range: float = 0.5    # 0 = bas du range, 1 = haut
    proche: object = None          # le niveau le plus proche du prix

    @property
    def sens_figures(self) -> str:
        h = sum(1 for f in self.figures if f.direction == "haussier")
        b = sum(1 for f in self.figures if f.direction == "baissier")
        return "haussier" if h > b else "baissier" if b > h else "neutre"


@dataclass
class Lecture:
    """La lecture complète d'un instrument, sur les 5 timeframes."""
    instrument: str
    par_tf: dict = field(default_factory=dict)
    accord: float = 0.0            # 0..1 — part des TF d'accord
    sens_dominant: str = "neutre"
    conflits: list = field(default_factory=list)
    niveaux_fusionnes: list = field(default_factory=list)
    attendu_sur_bruit: float = 0.0
    codes_uniques: list = field(default_factory=list)

    @property
    def n_figures(self) -> int:
        """Détections BRUTES, toutes échelles confondues."""
        return sum(len(l.figures) for l in self.par_tf.values())

    @property
    def n_uniques(self) -> int:
        """Figures DISTINCTES. C'est le seul chiffre comparable au bruit :
        `attendu_sur_bruit` est calculé sur des codes dédoublonnés, donc
        l'afficher à côté du total brut comparerait 11 à 0,8 alors que les
        deux ne comptent pas la même chose."""
        return len(self.codes_uniques)


# ==========================================================================
# 1. LES NIVEAUX — la partie descriptive, et la plus utile
# ==========================================================================
def niveaux(hauts, bas, tol: float = TOL_NIVEAU) -> list[Niveau]:
    """Les prix où le marché a tourné PLUSIEURS fois.

    Un niveau n'annonce rien : il constate. « Le prix a buté quatre fois
    entre 4 316 et 4 322 » est vérifiable sur l'historique, contrairement à
    « ce triangle annonce une hausse ». C'est pourquoi ces niveaux pèsent
    1,0 par défaut alors qu'une figure pèse 0,0.
    """
    hh, bb = pivots(hauts, bas)
    out: list[Niveau] = []
    for pts, genre in ((hh, "resistance"), (bb, "support")):
        restants = sorted(pts, key=lambda p: p[1])
        groupes: list[list] = []
        for i, v in restants:
            if groupes and abs(v - groupes[-1][-1][1]) / max(abs(v), 1e-9) <= tol:
                groupes[-1].append((i, v))
            else:
                groupes.append([(i, v)])
        for g in groupes:
            if len(g) < N_MIN_TOUCHES:
                continue
            prix = sum(v for _, v in g) / len(g)
            out.append(Niveau(prix, genre, len(g), max(i for i, _ in g),
                              min(1.0, len(g) / FORCE_MAX_TOUCHES)))
    return sorted(out, key=lambda n: -n.force)


def points_pivots(haut: float, bas: float, cloture: float) -> dict:
    """Points pivots classiques. Purement arithmétiques — aucune opinion.

    Ils sont sur tes planches, ils sont utilisés par beaucoup de monde, et
    c'est justement ce qui leur donne leur seul intérêt : ce ne sont pas des
    niveaux « vrais », ce sont des niveaux que d'autres regardent.
    """
    p = (haut + bas + cloture) / 3
    return {"P": p, "R1": 2 * p - bas, "S1": 2 * p - haut,
            "R2": p + (haut - bas), "S2": p - (haut - bas),
            "R3": haut + 2 * (p - bas), "S3": bas - 2 * (haut - p)}


def zone(niv: list[Niveau], prix: float, cote: str) -> Niveau | None:
    """Le niveau le plus proche au-dessus (resistance) ou au-dessous (support)."""
    cands = [n for n in niv
             if (n.prix > prix if cote == "haut" else n.prix < prix)]
    if not cands:
        return None
    return min(cands, key=lambda n: abs(n.prix - prix))


# ==========================================================================
# 2. LA LECTURE D'UN TIMEFRAME
# ==========================================================================
def lire_tf(tf: str, bougies) -> LectureTF:
    def ch(x, nom):
        return float(x.get(nom) if isinstance(x, dict) else getattr(x, nom))

    h = [ch(x, "high") for x in bougies]
    b = [ch(x, "low") for x in bougies]
    c = [ch(x, "close") for x in bougies]
    if len(c) < 15:
        return LectureTF(tf)

    niv = niveaux(h, b)
    prix = c[-1]

    # Tendance : pente de la régression sur les clôtures, en % par bougie.
    n = len(c); xs = list(range(n)); mx = (n - 1) / 2; my = sum(c) / n
    den = sum((x - mx) ** 2 for x in xs)
    pente = (sum((x - mx) * (y - my) for x, y in zip(xs, c)) / den / my
             if den and my else 0.0)
    total = pente * n            # parcours total sur la fenêtre
    tendance = ("haussier" if total > 0.02 else
                "baissier" if total < -0.02 else "neutre")

    plus_haut, plus_bas = max(h), min(b)
    pos = ((prix - plus_bas) / (plus_haut - plus_bas)
           if plus_haut > plus_bas else 0.5)

    return LectureTF(tf, detecter(bougies), niv, tendance,
                     round(total * 100, 2), round(pos, 3),
                     min((n for n in niv), key=lambda x: x.distance(prix),
                         default=None))


# ==========================================================================
# 3. LA LECTURE MULTI-TIMEFRAME
# ==========================================================================
def lire(instrument: str, bougies_par_tf: dict) -> Lecture:
    """La lecture complète. `bougies_par_tf` : {"H4": [...], "H1": [...], …}"""
    L = Lecture(instrument)
    for tf in TIMEFRAMES:
        if bougies_par_tf.get(tf):
            L.par_tf[tf] = lire_tf(tf, bougies_par_tf[tf])

    # --- accord des tendances, pondéré par échelle ----------------------
    poids_h = poids_b = 0.0
    for tf, l in L.par_tf.items():
        w = POIDS_TF.get(tf, 0.3)
        if l.tendance == "haussier":
            poids_h += w
        elif l.tendance == "baissier":
            poids_b += w
    total = poids_h + poids_b
    L.accord = round(max(poids_h, poids_b) / total, 3) if total else 0.0
    L.sens_dominant = ("haussier" if poids_h > poids_b else
                       "baissier" if poids_b > poids_h else "neutre")

    # --- les conflits : c'est l'information la plus utile ---------------
    for tf, l in L.par_tf.items():
        if l.tendance != "neutre" and l.tendance != L.sens_dominant \
                and L.sens_dominant != "neutre":
            L.conflits.append(f"{tf} est {l.tendance} alors que l'ensemble "
                              f"est {L.sens_dominant}")

    # --- figures : DÉDOUBLONNÉES entre timeframes ------------------------
    # Un double sommet sur H4 et sur H1 n'est PAS deux confirmations : H1
    # contient les mêmes bougies que H4, en plus fin. On ne garde qu'une
    # occurrence par code, celle du plus grand timeframe.
    vus: set = set()
    for tf in TIMEFRAMES:
        l = L.par_tf.get(tf)
        if not l:
            continue
        for f in l.figures:
            if f.code not in vus:
                vus.add(f.code)
                L.attendu_sur_bruit += TAUX_SUR_BRUIT.get(f.code, 0.05)
    L.codes_uniques = sorted(vus)
    L.attendu_sur_bruit = round(L.attendu_sur_bruit, 2)

    # --- niveaux fusionnés : le même prix vu sur plusieurs échelles ------
    fusion: dict = {}
    for tf, l in L.par_tf.items():
        w = POIDS_TF.get(tf, 0.3)
        for n in l.niveaux:
            cle = None
            for k in fusion:
                if abs(k - n.prix) / max(abs(k), 1e-9) <= TOL_NIVEAU:
                    cle = k
                    break
            if cle is None:
                fusion[n.prix] = [n, w, {tf}]
            else:
                fusion[cle][1] += w
                fusion[cle][2].add(tf)
    L.niveaux_fusionnes = sorted(
        ({"prix": n.prix, "genre": n.genre, "touches": n.touches,
          "poids": round(w, 2), "timeframes": sorted(tfs)}
         for n, w, tfs in fusion.values()),
        key=lambda x: -x["poids"])[:8]
    return L


# ==========================================================================
# 4. CE QU'IL DONNE AUX AUTRES AGENTS
# ==========================================================================
def source_direction(L: Lecture) -> dict:
    """Ce que AG-20 apporte à AG-19 Directeur — la partie DESCRIPTIVE.

    On donne la TENDANCE multi-timeframe (descriptive, poids 1,0), pas le
    biais des figures (prédictif, poids 0,0). Les figures partent déjà dans
    `figures_biais` par leur propre canal.
    """
    return {"ecart_ema": None,
            "sens": L.sens_dominant, "accord": L.accord,
            "mesure": (f"{len([l for l in L.par_tf.values() if l.tendance == L.sens_dominant])}"
                       f"/{len(L.par_tf)} timeframes {L.sens_dominant}"
                       f" · accord {L.accord:.0%}"),
            "conflits": L.conflits}


def arguments_avocats(L: Lecture, prix: float) -> list[dict]:
    """Ce que AG-20 apporte au débat AG-16 / AG-18.

    Uniquement des faits de NIVEAU, jamais de figure : un niveau se vérifie,
    une figure se croit.
    """
    out = []
    for n in L.niveaux_fusionnes[:3]:
        d = abs(prix - n["prix"]) / prix if prix else 1.0
        if d > 0.004:
            continue
        camp = "contre" if n["genre"] == "resistance" else "pour"
        out.append({
            "code": f"niveau_{n['genre']}_proche", "camp": camp,
            "famille": "structure",
            "texte": f"le prix est collé à une {n['genre']} testée "
                     f"{n['touches']} fois",
            "mesure": f"{n['prix']:.5g} à {d:.2%} · vue sur "
                      f"{', '.join(n['timeframes'])}",
            "force": min(1.0, n["poids"] / 2)})

    if L.conflits:
        out.append({
            "code": "timeframes_en_conflit", "camp": "contre",
            "famille": "structure",
            "texte": "les échelles de temps ne racontent pas la même histoire",
            "mesure": L.conflits[0],
            "force": min(1.0, len(L.conflits) / 3)})
    return out


def carte_agent(L: Lecture) -> dict:
    """La carte d'AG-20 pour le graphe et le panneau d'agents."""
    if not L.par_tf:
        return {"code": "AG-20", "statut": "MUET", "conviction": 0,
                "position": "neutre", "activites": ["aucune bougie reçue"]}

    # La conviction vient de l'ACCORD entre échelles, jamais du nombre de
    # figures : en voir beaucoup est la situation normale, pas un signal.
    conviction = int(round(L.accord * 100)) if L.sens_dominant != "neutre" else 0
    acts = [f"{L.sens_dominant} sur {L.accord:.0%} des échelles"]
    if L.niveaux_fusionnes:
        n = L.niveaux_fusionnes[0]
        acts.append(f"{n['genre']} majeure {n['prix']:.5g} "
                    f"({n['touches']} touches)")
    if L.conflits:
        acts.append(L.conflits[0])
    if L.n_uniques:
        acts.append(f"{L.n_uniques} figure(s) distincte(s) — le bruit en "
                    f"donnerait {L.attendu_sur_bruit:.1f}")

    return {"code": "AG-20", "statut": "STREAMING", "conviction": conviction,
            "position": ("pour" if L.sens_dominant == "haussier" else
                         "contre" if L.sens_dominant == "baissier" else "neutre"),
            "activites": acts}


def rapport(L: Lecture, prix: float | None = None) -> str:
    l = [f"# {L.instrument} — lecture graphique AG-20", ""]
    if not L.par_tf:
        return "\n".join(l + ["Aucune bougie reçue."]) + "\n"

    l += [f"**{L.sens_dominant}** sur {L.accord:.0%} des échelles "
          f"· {L.n_uniques} figure(s) distincte(s) "
          f"({L.n_figures} détections brutes)", ""]
    if L.attendu_sur_bruit:
        l += [f"> ⚠️ Du bruit pur donnerait **{L.attendu_sur_bruit:.1f}** "
              f"figure(s) distincte(s) — contre {L.n_uniques} ici. On compare "
              f"bien des distinctes à des distinctes : la même figure vue sur "
              f"H4 et sur H1 n'est pas deux observations, H1 contient les "
              f"mêmes bougies en plus fin.", ""]

    l += ["| TF | tendance | parcours | position range | figures |",
          "|---|---|---:|---:|---|"]
    for tf in TIMEFRAMES:
        x = L.par_tf.get(tf)
        if not x:
            l.append(f"| {tf} | — | — | — | *pas de données* |")
            continue
        l.append(f"| **{tf}** | {x.tendance} | {x.pente_pct:+.2f} % "
                 f"| {x.position_range:.0%} "
                 f"| {', '.join(f.code for f in x.figures) or '—'} |")

    if L.conflits:
        l += ["", "## Là où les échelles se contredisent", ""]
        l += [f"- {c}" for c in L.conflits]
        l += ["", "> C'est l'information la plus utile de cette lecture. Un "
              "accord parfait entre cinq échelles est rare et souvent "
              "trompeur ; un désaccord dit où se situe le risque."]

    if L.niveaux_fusionnes:
        l += ["", "## Niveaux — ce que le marché a réellement fait", "",
              "| prix | genre | touches | poids | vu sur |",
              "|---:|---|---:|---:|---|"]
        for n in L.niveaux_fusionnes:
            d = f" *(à {abs(prix - n['prix']) / prix:.2%})*" if prix else ""
            l.append(f"| **{n['prix']:.5g}**{d} | {n['genre']} "
                     f"| {n['touches']} | {n['poids']:.2f} "
                     f"| {', '.join(n['timeframes'])} |")
        l += ["", "> Un niveau **décrit** : le prix y a tourné, c'est "
              "vérifiable. Une figure **prédit** : la littérature dit "
              "majoritairement qu'elle se trompe. C'est pourquoi les niveaux "
              "pèsent 1,0 par défaut et les figures 0,0."]
    return "\n".join(l) + "\n"


# --------------------------------------------------------------------------
def _demo() -> None:
    import math, random
    rng = random.Random(21)

    def serie(n, f):
        out, px = [], 100.0
        for i in range(n):
            px = f(i, px)
            o = px * (1 + rng.uniform(-.001, .001))
            out.append({"open": o,
                        "high": max(o, px) * (1 + abs(rng.gauss(0, .0015))),
                        "low": min(o, px) * (1 - abs(rng.gauss(0, .0015))),
                        "close": px})
        return out

    # Marché qui monte sur les grandes échelles, corrige sur les petites.
    bougies = {
        "H4": serie(80, lambda i, p: 100 + i * 0.18 + math.sin(i / 4) * 1.2),
        "H1": serie(80, lambda i, p: 104 + i * 0.09 + math.sin(i / 3) * 1.0),
        "M30": serie(80, lambda i, p: 108 + i * 0.04 + math.sin(i / 3) * .9),
        "M15": serie(80, lambda i, p: 110 - i * 0.05 + math.sin(i / 4) * .8),
        "M5": serie(80, lambda i, p: 109 - i * 0.07 + math.sin(i / 3) * .6),
    }
    L = lire("XAU/USD", bougies)
    prix = bougies["M5"][-1]["close"]
    print(rapport(L, prix))

    print("=" * 74)
    print("  Carte d'agent :", carte_agent(L))
    print("\n  Vers AG-19 :", source_direction(L)["mesure"])
    print("\n  Vers les avocats :")
    for a in arguments_avocats(L, prix):
        print(f"    [{a['camp']}] {a['texte']} → {a['mesure']}")
    if not arguments_avocats(L, prix):
        print("    (rien — le prix n'est collé à aucun niveau)")

    print("\n" + "=" * 74)
    print("  Points pivots du jour :")
    h = max(x["high"] for x in bougies["H1"])
    b = min(x["low"] for x in bougies["H1"])
    c = bougies["H1"][-1]["close"]
    for k, v in points_pivots(h, b, c).items():
        print(f"    {k:<3} {v:10.4f}")


if __name__ == "__main__":
    _demo()
