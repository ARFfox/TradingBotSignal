#!/usr/bin/env python3
"""
FIGURES CHARTISTES — détection mécanique, et rien de plus.

    python3 figures.py        # démonstration

Ce que dit la recherche, avant d'écrire une ligne
--------------------------------------------------
Les figures chartistes sont le domaine le plus étudié et le plus décevant de
l'analyse technique. Trois mesures indépendantes, sur trois marchés :

  · BULKOWSKI — ~13 900 figures, 23 types, 1991-2008. Le taux d'échec a
    DOUBLÉ : 14 % en 1990, 28 % en 2003-2007, 44 % au pic de 2007, et
    seulement pour atteindre +10 %. « Les figures échouent deux à quatre
    fois plus souvent qu'avant. »

  · ROBERTS & al. (Cambridge) — 8 ans de tick GBP/USD, échantillon
    d'apprentissage et de test séparés, 5 échelles de temps. Verdict :
    l'épaule-tête-épaule est « PERDANTE quand on la trade de façon
    systématique et réaliste » — de −28 à −37 pips de moyenne, sur les
    5 échelles, sans exception.

  · LO, MAMAYSKY & WANG (Journal of Finance, 2000) — les figures portent
    « une information incrémentale » mais la rentabilité après coûts n'est
    pas établie. Leur apport réel : rendre la détection AUTOMATIQUE, parce
    que « la nature très subjective de l'analyse technique » était l'obstacle.

  · Bougies japonaises, S&P 500, 1950-2017 — aucun pouvoir prédictif sur les
    cours de CLÔTURE. Un peu sur les extrêmes (le bas du marteau marque un
    creux temporaire), rien sur la direction qui suit.

Ce que ce module fait de cette information
-------------------------------------------
Il détecte. **Il n'émet aucun signal, jamais.** Une figure sort d'ici comme
un FAIT mesuré — « triangle ascendant, 5 touches, résistance à 0.4 % près » —
et elle entre dans le débat des avocats comme n'importe quel autre argument,
où `calibrer()` lui donnera le poids qu'elle mérite sur TON journal.

⚠️ **Le poids par défaut d'une figure est ZÉRO, pas 1,0.** C'est la
différence avec `avocats.py`, et elle est délibérée : les arguments des
avocats reposent sur de la mécanique vérifiable (un stop dans le bruit se
fait toucher). Une figure repose sur une littérature qui dit majoritairement
« pas d'edge ». Elle doit donc gagner sa place par la mesure avant de parler.

Le seul résultat encourageant de toute cette littérature est celui de
Cambridge : **le filtre sur les ATTRIBUTS de la figure a amélioré 69 % des
cas, alors que la figure seule perdait.** Pas « épaule-tête-épaule », mais
« épaule-tête-épaule AVEC telle proportion et tel volume ». C'est exactement
la découpe que fait `chercheur_sous_ensembles.py`. D'où `mesures` : chaque
figure porte ses attributs chiffrés pour qu'ils puissent être testés.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
K_PIVOT = 3            # bougies de chaque côté pour valider un sommet/creux
TOL = 0.004            # 0,4 % — tolérance d'alignement sur une droite

N_MIN_FIGURE = 30      # observations avant qu'une figure ait le droit de peser
Z_BRUIT = 1.64
R_REFERENCE = 0.50
POIDS_DEFAUT = 0.0     # ⚠️ une figure non mesurée ne vote pas
POIDS_MAX = 2.0
PLAFOND_R = 10.0

FAMILLES = ("continuation", "retournement", "bilateral", "bougie")

# --------------------------------------------------------------------------
# LE CHIFFRE QUI CHANGE TOUT — mesuré par `mesurer_bruit()`, 2 000 marches
# au hasard de 80 bougies, sans aucune tendance ni structure.
#
#   98,3 % des graphiques PUREMENT ALÉATOIRES contiennent au moins une figure.
#   2,94 figures par graphique en moyenne.
#
# ⚠️ CE CHIFFRE A EMPIRÉ QUAND ON A AJOUTÉ DES FIGURES, et c'est la leçon.
# Avec 17 figures détectées : 90,0 % du bruit, 1,68 figure par graphique.
# Avec 34 figures détectées : 98,3 % du bruit, 2,94 figures par graphique.
#
# Doubler le catalogue n'a PAS doublé la capacité de lecture du marché : ça a
# doublé le nombre de façons de trouver quelque chose dans du hasard pur. Sur
# un graphique aléatoire de 80 bougies, on voit désormais presque toujours
# trois figures. C'est exactement pour ça qu'aucune ne pèse tant qu'elle n'a
# pas été mesurée sur le journal.
#
# Un double sommet apparaît dans 28,9 % du bruit. Une épaule-tête-épaule dans
# 8,4 %. Voir une figure n'est donc PAS une information : c'est la situation
# normale. La question utile n'est jamais « est-ce que je vois un triangle »,
# c'est « est-ce que ce triangle arrive plus souvent que dans du bruit, et
# est-ce qu'il précède un gain ».
#
# C'est l'exact équivalent des 32,4 % de la marche au hasard pour le taux de
# réussite : la référence sans laquelle un chiffre ne veut rien dire.
# --------------------------------------------------------------------------
TAUX_SUR_BRUIT = {
    "double_sommet": 0.289, "toupie": 0.261, "etoile_filante": 0.219,
    "marteau": 0.208, "triple_sommet": 0.208, "double_creux": 0.200,
    "arrondi_creux": 0.155, "triple_creux": 0.153, "biseau_descendant": 0.145,
    "arrondi_sommet": 0.133, "doji": 0.123, "biseau_ascendant": 0.119,
    "tete_epaules": 0.084, "canal_haussier": 0.072,
    "tete_epaules_inverse": 0.067, "canal_baissier": 0.067,
    "elargissement": 0.062, "triangle_symetrique": 0.059, "tasse_anse": 0.055,
    "triangle_descendant": 0.054, "triangle_ascendant": 0.051,
    "pendu": 0.031, "marteau_inverse": 0.028, "rectangle": 0.025,
    "etoile_du_soir": 0.018, "etoile_du_matin": 0.013,
    "drapeau_haussier": 0.013, "drapeau_baissier": 0.012,
    "penetrante": 0.007, "couverture_nuages": 0.006,
    "englobante_baissiere": 0.004, "englobante_haussiere": 0.003,
    "trois_soldats": 0.002, "trois_corbeaux": 0.002,
}
AU_MOINS_UNE_SUR_BRUIT = 0.983
FIGURES_PAR_GRAPHIQUE_BRUIT = 2.94


@dataclass
class Figure:
    code: str
    famille: str
    direction: str        # "haussier" | "baissier" | "indetermine"
    debut: int
    fin: int
    qualite: float        # 0..1 — NETTETÉ géométrique, jamais une confiance
    mesures: dict = field(default_factory=dict)

    def __str__(self) -> str:
        m = " · ".join(f"{k} {v}" for k, v in self.mesures.items())
        return (f"{self.code} ({self.direction}, netteté {self.qualite:.2f})"
                + (f" — {m}" if m else ""))


# ==========================================================================
# 1. LES OUTILS DE BASE
# ==========================================================================
def pivots(hauts, bas, k: int = K_PIVOT):
    """Sommets et creux : un point plus extrême que ses k voisins de chaque côté.

    C'est LA définition qui rend tout le reste objectif. Sans elle, « je vois
    un triangle » dépend de qui regarde — et c'est précisément l'obstacle que
    Lo, Mamaysky & Wang ont dû lever pour pouvoir mesurer quoi que ce soit.
    """
    hh, bb = [], []
    for i in range(k, len(hauts) - k):
        # Égalités : on garde la PREMIÈRE occurrence du plateau au lieu de
        # rejeter le pivot. Exiger un extrême strictement unique paraît plus
        # propre, mais supprime justement les cas les plus nets — un double
        # sommet exact, un retest au centime près, un chiffre rond. Le
        # premier jeu de tests l'a montré : plus aucun rectangle ni triangle
        # n'était détecté sur des sommets parfaitement alignés.
        f = hauts[i - k:i + k + 1]
        if hauts[i] == max(f) and hauts[i] > max(f[:k] or [float("-inf")]):
            hh.append((i, hauts[i]))
        f = bas[i - k:i + k + 1]
        if bas[i] == min(f) and bas[i] < min(f[:k] or [float("inf")]):
            bb.append((i, bas[i]))
    return hh, bb


def droite(points):
    """Régression sur des pivots. Renvoie (pente_relative, ordonnée, R²).

    La pente est RELATIVE au niveau de prix : +0.001 veut dire « +0,1 % par
    bougie », ce qui se compare entre l'or à 4 300 et EUR/USD à 1,08. Une
    pente absolue ne se compare à rien.
    """
    n = len(points)
    if n < 2:
        return 0.0, 0.0, 0.0
    sx = sum(p[0] for p in points); sy = sum(p[1] for p in points)
    mx, my = sx / n, sy / n
    num = sum((p[0] - mx) * (p[1] - my) for p in points)
    den = sum((p[0] - mx) ** 2 for p in points)
    if den == 0 or my == 0:
        return 0.0, my, 0.0
    a = num / den
    b = my - a * mx
    st = sum((p[1] - my) ** 2 for p in points)
    sr = sum((p[1] - (a * p[0] + b)) ** 2 for p in points)
    r2 = 1 - sr / st if st > 0 else 0.0
    return a / my, b, max(0.0, r2)


def _deplacement(pente, span, hauteur_rel) -> float:
    """Ce que la droite parcourt sur toute la figure, en fraction de sa hauteur.

    ⚠️ C'est LA mesure qui remplace un seuil absolu sur la pente, et le
    premier jeu de tests a montré pourquoi : une pente de 0,12 % par bougie
    passait sous `PLAT_MAX` et une résistance qui montait de 3,6 % sur
    30 bougies était déclarée « horizontale ». Un triangle ascendant
    devenait un rectangle.

    Une pente n'est ni plate ni raide dans l'absolu — elle l'est par rapport
    à la HAUTEUR de la figure et à sa DURÉE. 0,12 % par bougie sur 3 bougies
    est du bruit ; sur 30 bougies, c'est la figure entière.
    """
    if hauteur_rel <= 0:
        return 0.0
    return pente * span / hauteur_rel


PLAT = 0.25      # sous 25 % de la hauteur parcourue : la droite est plate
PENTE = 0.35     # au-delà : elle monte ou descend franchement


# ==========================================================================
# 2. LES FIGURES DE PRIX
# ==========================================================================
def _triangle(hh, bb, n) -> Figure | None:
    if len(hh) < 2 or len(bb) < 2:
        return None
    H, B = hh[-3:], bb[-3:]
    ph, _, r2h = droite(H)
    pb, _, r2b = droite(B)
    qualite = min(1.0, (r2h + r2b) / 2)
    debut = min(H[0][0], B[0][0])
    fin = max(hh[-1][0], bb[-1][0])
    span = max(1, fin - debut)

    hm = sum(p[1] for p in H) / len(H)
    bm = sum(p[1] for p in B) / len(B)
    if bm <= 0 or hm <= bm:
        return None
    hauteur = (hm - bm) / bm                 # hauteur relative de la figure
    dh = _deplacement(ph, span, hauteur)     # parcours de la résistance
    db = _deplacement(pb, span, hauteur)     # parcours du support

    base = dict(parcours_haut=round(dh, 2), parcours_bas=round(db, 2),
                hauteur_pct=round(hauteur * 100, 2),
                touches=len(H) + len(B))

    if abs(dh) < PLAT and db > PENTE:
        return Figure("triangle_ascendant", "bilateral", "haussier",
                      debut, fin, qualite, base)
    if abs(db) < PLAT and dh < -PENTE:
        return Figure("triangle_descendant", "bilateral", "baissier",
                      debut, fin, qualite, base)
    if dh < -PENTE and db > PENTE:
        # ⚠️ AUCUNE direction. Les fiches qui circulent affirment « on sait
        # que le prix va sortir » — c'est vrai, et ça ne dit rien : elles ne
        # disent pas de quel côté. Un triangle symétrique est une mesure de
        # compression, pas une prévision.
        return Figure("triangle_symetrique", "bilateral", "indetermine",
                      debut, fin, qualite, base)
    if dh > PENTE and db > PENTE and dh < db:
        return Figure("biseau_ascendant", "retournement", "baissier",
                      debut, fin, qualite, base)
    if dh < -PENTE and db < -PENTE and dh > db:
        return Figure("biseau_descendant", "retournement", "haussier",
                      debut, fin, qualite, base)
    return None


def _rectangle(hh, bb) -> Figure | None:
    if len(hh) < 2 or len(bb) < 2:
        return None
    H, B = hh[-3:], bb[-3:]
    ph, _, _ = droite(H); pb, _, _ = droite(B)
    haut = sum(p[1] for p in H) / len(H)
    bas_ = sum(p[1] for p in B) / len(B)
    if bas_ <= 0 or haut <= bas_:
        return None
    hauteur = (haut - bas_) / bas_
    span = max(1, max(hh[-1][0], bb[-1][0]) - min(H[0][0], B[0][0]))
    if abs(_deplacement(ph, span, hauteur)) >= PLAT or \
       abs(_deplacement(pb, span, hauteur)) >= PLAT:
        return None
    dispersion = max(
        max(abs(p[1] - haut) / haut for p in hh[-3:]),
        max(abs(p[1] - bas_) / bas_ for p in bb[-3:]))
    if dispersion > TOL * 2:
        return None
    return Figure("rectangle", "continuation", "indetermine",
                  min(hh[-3:][0][0], bb[-3:][0][0]), max(hh[-1][0], bb[-1][0]),
                  max(0.0, 1 - dispersion / (TOL * 2)),
                  dict(hauteur_pct=round((haut - bas_) / bas_ * 100, 2),
                       touches=len(hh[-3:]) + len(bb[-3:])))


def _double(hh, bb) -> Figure | None:
    """Double sommet / double creux : deux extrêmes au même niveau."""
    for pts, code, sens in ((hh, "double_sommet", "baissier"),
                            (bb, "double_creux", "haussier")):
        if len(pts) < 2:
            continue
        (i1, v1), (i2, v2) = pts[-2], pts[-1]
        if v1 == 0 or i2 - i1 < 5:
            continue
        ecart = abs(v2 - v1) / abs(v1)
        if ecart <= TOL * 1.5:
            return Figure(code, "retournement", sens, i1, i2,
                          max(0.0, 1 - ecart / (TOL * 1.5)),
                          dict(ecart_pct=round(ecart * 100, 3),
                               largeur_bougies=i2 - i1))
    return None


def _tete_epaules(hh, bb) -> Figure | None:
    """Épaule-tête-épaule et son inverse.

    ⚠️ La figure la plus enseignée, et la seule dont l'échec ait été mesuré
    proprement hors échantillon : Roberts & al. la trouvent PERDANTE sur les
    5 échelles de temps testées, de −28 à −37 pips. On la détecte quand même,
    parce que la mesurer sur TON journal vaut mieux que la croire ou la
    rejeter sur parole — mais son poids par défaut reste zéro.
    """
    for pts, code, sens, pire in ((hh, "tete_epaules", "baissier", max),
                                  (bb, "tete_epaules_inverse", "haussier", min)):
        if len(pts) < 3:
            continue
        (ig, vg), (it, vt), (id_, vd) = pts[-3:]
        if vt != pire(vg, vt, vd) or vg == 0:
            continue
        sym = abs(vd - vg) / abs(vg)
        proem = abs(vt - (vg + vd) / 2) / abs((vg + vd) / 2)
        if sym > TOL * 3 or proem < TOL * 2:
            continue
        return Figure(code, "retournement", sens, ig, id_,
                      max(0.0, 1 - sym / (TOL * 3)),
                      dict(asymetrie_pct=round(sym * 100, 2),
                           proeminence_pct=round(proem * 100, 2)))
    return None


def _drapeau(cloture, hh, bb) -> Figure | None:
    """Drapeau / fanion : une impulsion franche, puis une consolidation
    courte et contraire. La mesure qui compte est le RAPPORT entre les
    deux — sans impulsion, il n'y a pas de drapeau, juste du bruit."""
    if len(cloture) < 25 or len(hh) < 2 or len(bb) < 2:
        return None
    dep = min(hh[-2][0], bb[-2][0])
    if dep < 10:
        return None
    a, b = cloture[max(0, dep - 12)], cloture[dep]
    if a == 0:
        return None
    impulsion = (b - a) / a
    if abs(impulsion) < 0.01:
        return None
    seg = cloture[dep:]
    if len(seg) < 4 or seg[0] == 0:
        return None
    retrait = (seg[-1] - seg[0]) / seg[0]
    amplitude = (max(seg) - min(seg)) / seg[0]
    if amplitude > abs(impulsion) * 0.6:
        return None
    if impulsion > 0 and retrait < 0:
        sens, code = "haussier", "drapeau_haussier"
    elif impulsion < 0 and retrait > 0:
        sens, code = "baissier", "drapeau_baissier"
    else:
        return None
    return Figure(code, "continuation", sens, dep - 12, len(cloture) - 1,
                  min(1.0, abs(impulsion) / (amplitude + 1e-9) / 5),
                  dict(impulsion_pct=round(impulsion * 100, 2),
                       consolidation_pct=round(amplitude * 100, 2)))


def _triple(hh, bb) -> Figure | None:
    """Triple sommet / triple creux : trois extrêmes au même niveau."""
    for pts, code, sens in ((hh, "triple_sommet", "baissier"),
                            (bb, "triple_creux", "haussier")):
        if len(pts) < 3:
            continue
        (i1, v1), (i2, v2), (i3, v3) = pts[-3:]
        if v1 == 0 or i3 - i1 < 10:
            continue
        moy = (v1 + v2 + v3) / 3
        ecart = max(abs(v - moy) for v in (v1, v2, v3)) / abs(moy)
        if ecart <= TOL * 1.5:
            return Figure(code, "retournement", sens, i1, i3,
                          max(0.0, 1 - ecart / (TOL * 1.5)),
                          dict(dispersion_pct=round(ecart * 100, 3),
                               largeur_bougies=i3 - i1))
    return None


def _elargissement(hh, bb) -> Figure | None:
    """Élargissement (« vuvuzela ») : sommets qui montent ET creux qui
    descendent. Le contraire d'un triangle — la volatilité augmente."""
    if len(hh) < 3 or len(bb) < 3:
        return None
    H, B = hh[-3:], bb[-3:]
    ph, _, r2h = droite(H); pb, _, r2b = droite(B)
    hm = sum(x[1] for x in H) / 3; bm = sum(x[1] for x in B) / 3
    if bm <= 0 or hm <= bm:
        return None
    hauteur = (hm - bm) / bm
    debut = min(H[0][0], B[0][0]); fin = max(hh[-1][0], bb[-1][0])
    span = max(1, fin - debut)
    dh = _deplacement(ph, span, hauteur); db = _deplacement(pb, span, hauteur)
    if dh > PENTE and db < -PENTE:
        # Aucune direction : la figure dit que ça bouge, pas où ça va.
        return Figure("elargissement", "bilateral", "indetermine", debut, fin,
                      min(1.0, (r2h + r2b) / 2),
                      dict(parcours_haut=round(dh, 2),
                           parcours_bas=round(db, 2),
                           hauteur_pct=round(hauteur * 100, 2)))
    return None


def _canal(hh, bb) -> Figure | None:
    """Canal : deux droites parallèles qui montent ou descendent ensemble."""
    if len(hh) < 3 or len(bb) < 3:
        return None
    H, B = hh[-3:], bb[-3:]
    ph, _, r2h = droite(H); pb, _, r2b = droite(B)
    if r2h < 0.7 or r2b < 0.7:
        return None
    hm = sum(x[1] for x in H) / 3; bm = sum(x[1] for x in B) / 3
    if bm <= 0 or hm <= bm:
        return None
    hauteur = (hm - bm) / bm
    debut = min(H[0][0], B[0][0]); fin = max(hh[-1][0], bb[-1][0])
    span = max(1, fin - debut)
    dh = _deplacement(ph, span, hauteur); db = _deplacement(pb, span, hauteur)
    # Parallèles : les deux droites parcourent à peu près la même distance.
    if abs(dh - db) > 0.4 or abs(dh) < PENTE:
        return None
    return Figure("canal_haussier" if dh > 0 else "canal_baissier",
                  "continuation", "haussier" if dh > 0 else "baissier",
                  debut, fin, min(1.0, (r2h + r2b) / 2),
                  dict(parcours=round(dh, 2), parallelisme=round(abs(dh - db), 2),
                       hauteur_pct=round(hauteur * 100, 2)))


def _arrondi(cloture) -> Figure | None:
    """Sommet / creux arrondi : un demi-tour progressif, sans pic.

    On l'identifie par la COURBURE : on ajuste une parabole sur la fenêtre.
    Un `a` positif creuse (creux arrondi), négatif bombe (sommet arrondi).
    """
    n = len(cloture)
    if n < 30:
        return None
    seg = cloture[-40:] if n >= 40 else cloture[:]
    m = len(seg); moy = sum(seg) / m
    if moy <= 0:
        return None
    xs = [i - (m - 1) / 2 for i in range(m)]
    # Ajustement quadratique par moindres carrés (base orthogonale simple).
    sx2 = sum(x * x for x in xs); sx4 = sum(x ** 4 for x in xs)
    sy = sum(seg); sx2y = sum(x * x * y for x, y in zip(xs, seg))
    den = m * sx4 - sx2 * sx2
    if den == 0:
        return None
    a = (m * sx2y - sx2 * sy) / den
    # Courbure relative : `a` × (demi-largeur)² rapporté au niveau de prix.
    courbure = a * ((m / 2) ** 2) / moy
    if abs(courbure) < 0.015:
        return None
    # La pente aux deux bouts doit s'inverser, sinon c'est une tendance.
    g = seg[m // 4] - seg[0]; d = seg[-1] - seg[3 * m // 4]
    if g * d >= 0:
        return None
    return Figure("arrondi_creux" if a > 0 else "arrondi_sommet",
                  "retournement", "haussier" if a > 0 else "baissier",
                  n - m, n - 1, min(1.0, abs(courbure) / 0.05),
                  dict(courbure_pct=round(courbure * 100, 2), fenetre=m))


def _tasse_anse(cloture, hh, bb) -> Figure | None:
    """Tasse avec anse : un creux arrondi, puis un petit repli court.

    ⚠️ C'est la figure la plus subjective du lot — « où commence l'anse »
    n'a pas de définition consensuelle. Celle-ci est mécanique et donc
    discutable : creux arrondi sur les 40 bougies précédentes, puis un repli
    d'au plus 15 bougies et d'au plus la moitié de la profondeur de la tasse.
    """
    n = len(cloture)
    if n < 55:
        return None
    tasse = _arrondi(cloture[:-12])
    if not tasse or tasse.code != "arrondi_creux":
        return None
    anse = cloture[-12:]
    if not anse or anse[0] <= 0:
        return None
    profondeur_anse = (max(anse) - min(anse)) / anse[0]
    bord = max(cloture[-40:-12]) if n >= 52 else max(cloture[:-12])
    profondeur_tasse = (bord - min(cloture[-40:-12])) / bord if bord else 0
    if profondeur_tasse <= 0 or profondeur_anse > profondeur_tasse * 0.5:
        return None
    return Figure("tasse_anse", "continuation", "haussier", n - 52, n - 1,
                  min(1.0, 1 - profondeur_anse / (profondeur_tasse * 0.5)),
                  dict(tasse_pct=round(profondeur_tasse * 100, 2),
                       anse_pct=round(profondeur_anse * 100, 2)))

# ==========================================================================
# 3. LES BOUGIES
# ==========================================================================
def _bougies(o, h, b, c) -> list[Figure]:
    """Figures en bougies, sur les 3 dernières seulement.

    ⚠️ Sur le S&P 500 de 1950 à 2017, marteau et étoile filante n'ont AUCUN
    pouvoir prédictif sur les cours de clôture. Ils en ont un peu sur les
    EXTRÊMES : le bas d'un marteau marque souvent un creux temporaire. Ce
    n'est pas une direction, c'est un niveau. On les détecte comme contexte.
    """
    out, n = [], len(c)
    if n < 3:
        return out
    i = n - 1
    corps = abs(c[i] - o[i]); etendue = h[i] - b[i]
    if etendue <= 0:
        return out
    haut_m = h[i] - max(c[i], o[i])
    bas_m = min(c[i], o[i]) - b[i]

    # ⚠️ L'ORDRE COMPTE. Marteau et étoile filante ont un petit corps par
    # définition : les tester APRÈS le doji fait que le doji les avale tous.
    # Le doji est le cas où AUCUNE mèche ne domine — c'est un reste, pas une
    # priorité.
    if bas_m > max(corps * 2, haut_m * 2) and bas_m / etendue > 0.5:
        out.append(Figure("marteau", "bougie", "haussier", i, i,
                          min(1.0, bas_m / etendue),
                          dict(meche_basse_x=round(bas_m / max(corps, 1e-9), 1))))
    elif haut_m > max(corps * 2, bas_m * 2) and haut_m / etendue > 0.5:
        out.append(Figure("etoile_filante", "bougie", "baissier", i, i,
                          min(1.0, haut_m / etendue),
                          dict(meche_haute_x=round(haut_m / max(corps, 1e-9), 1))))
    elif corps / etendue < 0.1:
        out.append(Figure("doji", "bougie", "indetermine", i, i,
                          1 - corps / etendue,
                          dict(corps_pct=round(corps / etendue * 100, 1))))

    cp = abs(c[i - 1] - o[i - 1])
    if cp > 0 and corps > cp:
        if c[i] > o[i] and c[i - 1] < o[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1]:
            out.append(Figure("englobante_haussiere", "bougie", "haussier",
                              i - 1, i, min(1.0, corps / cp / 3),
                              dict(rapport_corps=round(corps / cp, 2))))
        elif c[i] < o[i] and c[i - 1] > o[i - 1] and o[i] >= c[i - 1] and c[i] <= o[i - 1]:
            out.append(Figure("englobante_baissiere", "bougie", "baissier",
                              i - 1, i, min(1.0, corps / cp / 3),
                              dict(rapport_corps=round(corps / cp, 2))))

    # --- marteau inversé / pendu : même forme, contexte opposé -----------
    # Le contexte (tendance précédente) fait toute la différence, et c'est
    # mesurable : on regarde les 10 bougies qui précèdent.
    if n >= 12:
        avant = c[i - 10:i]
        tendance = (avant[-1] - avant[0]) / avant[0] if avant[0] else 0.0
        if haut_m > corps * 2 and bas_m < corps and tendance < -0.01:
            out.append(Figure("marteau_inverse", "bougie", "haussier", i, i,
                              min(1.0, haut_m / etendue),
                              dict(tendance_avant_pct=round(tendance * 100, 2))))
        elif bas_m > corps * 2 and haut_m < corps and tendance > 0.01:
            out.append(Figure("pendu", "bougie", "baissier", i, i,
                              min(1.0, bas_m / etendue),
                              dict(tendance_avant_pct=round(tendance * 100, 2))))

    # --- toupie : petit corps, deux mèches ÉQUILIBRÉES -------------------
    if corps / etendue < 0.3 and bas_m > corps and haut_m > corps \
            and 0.6 < (haut_m / bas_m if bas_m else 9) < 1.7:
        out.append(Figure("toupie", "bougie", "indetermine", i, i,
                          1 - corps / etendue,
                          dict(corps_pct=round(corps / etendue * 100, 1))))

    # --- pénétrante / couverture en nuages -------------------------------
    if cp > 0 and corps > cp * 0.5:
        mil = (o[i - 1] + c[i - 1]) / 2
        if c[i] > o[i] and c[i - 1] < o[i - 1] and o[i] < c[i - 1] and c[i] > mil:
            out.append(Figure("penetrante", "bougie", "haussier", i - 1, i,
                              min(1.0, (c[i] - mil) / (o[i - 1] - c[i - 1])),
                              dict(penetration_pct=round(
                                  (c[i] - c[i - 1]) / (o[i - 1] - c[i - 1]) * 100, 1))))
        elif c[i] < o[i] and c[i - 1] > o[i - 1] and o[i] > c[i - 1] and c[i] < mil:
            out.append(Figure("couverture_nuages", "bougie", "baissier", i - 1, i,
                              min(1.0, (mil - c[i]) / (c[i - 1] - o[i - 1])),
                              dict(penetration_pct=round(
                                  (c[i - 1] - c[i]) / (c[i - 1] - o[i - 1]) * 100, 1))))

    # --- figures à trois bougies -----------------------------------------
    if n >= 3:
        c1, c2, c3 = (abs(c[i - 2] - o[i - 2]), abs(c[i - 1] - o[i - 1]), corps)
        hausse = [c[k] > o[k] for k in (i - 2, i - 1, i)]
        e1 = h[i - 2] - b[i - 2]; e2 = h[i - 1] - b[i - 1]
        # étoile du matin / du soir : grande · petite · grande inversée
        if e1 > 0 and e2 > 0 and c2 < c1 * 0.4 and c2 < c3 * 0.4:
            if not hausse[0] and hausse[2] and c[i] > (o[i - 2] + c[i - 2]) / 2:
                out.append(Figure("etoile_du_matin", "bougie", "haussier",
                                  i - 2, i, min(1.0, 1 - c2 / max(c1, 1e-9)),
                                  dict(corps_central_pct=round(c2 / e2 * 100, 1))))
            elif hausse[0] and not hausse[2] and c[i] < (o[i - 2] + c[i - 2]) / 2:
                out.append(Figure("etoile_du_soir", "bougie", "baissier",
                                  i - 2, i, min(1.0, 1 - c2 / max(c1, 1e-9)),
                                  dict(corps_central_pct=round(c2 / e2 * 100, 1))))
        # trois soldats / trois corbeaux : trois corps pleins dans le sens
        elif all(hausse) and c[i] > c[i - 1] > c[i - 2] \
                and min(c1, c2, c3) > 0 and e1 > 0 \
                and all(x > 0.5 * y for x, y in ((c1, e1), (c2, e2), (c3, etendue))):
            out.append(Figure("trois_soldats", "bougie", "haussier", i - 2, i,
                              min(1.0, c3 / etendue),
                              dict(progression_pct=round(
                                  (c[i] - c[i - 2]) / c[i - 2] * 100, 2))))
        elif not any(hausse) and c[i] < c[i - 1] < c[i - 2] \
                and min(c1, c2, c3) > 0 and e1 > 0 \
                and all(x > 0.5 * y for x, y in ((c1, e1), (c2, e2), (c3, etendue))):
            out.append(Figure("trois_corbeaux", "bougie", "baissier", i - 2, i,
                              min(1.0, c3 / etendue),
                              dict(progression_pct=round(
                                  (c[i] - c[i - 2]) / c[i - 2] * 100, 2))))
    return out


# ==========================================================================
# 4. LE POINT D'ENTRÉE
# ==========================================================================
def detecter(bougies, k: int = K_PIVOT) -> list[Figure]:
    """Toutes les figures présentes à la DERNIÈRE bougie.

    `bougies` : liste de dicts {open, high, low, close} ou d'objets.

    ⚠️ Aucune figure n'est cherchée dans le futur : toutes les mesures
    s'arrêtent à la dernière bougie fournie. Une détection qui regarde une
    bougie de plus produit un backtest magnifique et inutilisable.
    """
    def ch(x, nom):
        return x.get(nom) if isinstance(x, dict) else getattr(x, nom)

    o = [float(ch(x, "open")) for x in bougies]
    h = [float(ch(x, "high")) for x in bougies]
    b = [float(ch(x, "low")) for x in bougies]
    c = [float(ch(x, "close")) for x in bougies]
    if len(c) < 2 * k + 3:
        return []

    hh, bb = pivots(h, b, k)
    trouvees = [f for f in (_triangle(hh, bb, len(c)), _rectangle(hh, bb),
                            _double(hh, bb), _triple(hh, bb),
                            _tete_epaules(hh, bb), _drapeau(c, hh, bb),
                            _elargissement(hh, bb), _canal(hh, bb),
                            _arrondi(c), _tasse_anse(c, hh, bb)) if f]
    return trouvees + _bougies(o, h, b, c)


def biais(figures: list[Figure], poids: dict[str, float] | None = None) -> dict:
    """Le biais directionnel porté par les figures — RIEN de plus.

    Sans `poids` mesurés, le résultat est **toujours neutre avec un score de
    zéro**. Ce n'est pas une panne : c'est le module qui refuse de donner une
    direction sur la foi d'une figure dont personne n'a vérifié qu'elle
    prédit quoi que ce soit sur ce marché.
    """
    p = poids or {}
    haut = sum(f.qualite * p.get(f.code, POIDS_DEFAUT)
               for f in figures if f.direction == "haussier")
    bas = sum(f.qualite * p.get(f.code, POIDS_DEFAUT)
              for f in figures if f.direction == "baissier")
    brut = haut - bas
    score = max(-1.0, min(1.0, brut / (1.0 + abs(brut))))
    sens = "haussier" if score > 0.15 else "baissier" if score < -0.15 else "neutre"
    mesurees = sum(1 for f in figures if p.get(f.code, 0.0) > 0)
    # Probabilité de voir AU MOINS autant de figures dans du bruit pur.
    # Trois figures sur un graphique n'est pas remarquable : c'est la norme.
    attendu = sum(TAUX_SUR_BRUIT.get(f.code, 0.05) for f in figures)
    return {"sens": sens, "score": round(score, 3),
            "n_figures": len(figures), "n_mesurees": mesurees,
            "figures": [f.code for f in figures],
            "attendu_sur_bruit": round(attendu, 2),
            "motif": ("aucune figure mesurée sur ce marché — biais neutre"
                      if not mesurees else
                      f"{mesurees}/{len(figures)} figure(s) au poids mesuré")}


# ==========================================================================
# 5. CALIBRATION — une figure gagne sa place ou se tait
# ==========================================================================
@dataclass
class PoidsFigure:
    code: str
    poids: float
    n: int
    r_present: float
    r_absent: float
    verdict: str


def calibrer(paires) -> dict[str, PoidsFigure]:
    """`paires` : liste de (signal résolu, [figures présentes à l'émission]).

    Même logique que `avocats.calibrer()`, avec deux différences assumées :
    le seuil est plus haut (30 au lieu de 25) et le poids par défaut est
    ZÉRO. Une figure qu'on n'a pas mesurée ne parle pas.
    """
    r_par_code: dict[str, list[float]] = defaultdict(list)
    sens_par_code: dict[str, str] = {}
    tous: list[float] = []

    for s, figs in paires:
        st = s.get("statut") if isinstance(s, dict) else getattr(s, "statut", None)
        if st not in ("TP", "SL"):
            continue
        r = s.get("r_realise") if isinstance(s, dict) else getattr(s, "r_realise", None)
        if r is None:
            continue
        r = max(-PLAFOND_R, min(PLAFOND_R, float(r)))
        tous.append(r)
        for f in figs:
            code = f.code if isinstance(f, Figure) else str(f)
            sens_par_code.setdefault(code, getattr(f, "direction", "?"))
            r_par_code[code].append(r)

    out: dict[str, PoidsFigure] = {}
    n_tot, somme = len(tous), sum(tous)
    carres = sum(x * x for x in tous)

    for code, rs in r_par_code.items():
        n = len(rs); s_p = sum(rs); sc_p = sum(x * x for x in rs)
        r_pres = s_p / n
        n_abs = n_tot - n
        r_abs = (somme - s_p) / n_abs if n_abs else 0.0
        ecart = r_pres - r_abs

        v_p = max(0.0, sc_p / n - r_pres ** 2)
        v_a = max(0.0, (carres - sc_p) / n_abs - r_abs ** 2) if n_abs else 0.0
        marge = Z_BRUIT * (v_p / n + (v_a / n_abs if n_abs else 0.0)) ** 0.5

        if n < N_MIN_FIGURE:
            poids, verdict = POIDS_DEFAUT, f"non mesurée ({n}/{N_MIN_FIGURE})"
        elif ecart <= -marge:
            poids, verdict = POIDS_DEFAUT, "à retourner — elle prédit l'inverse"
        elif ecart <= marge:
            poids, verdict = POIDS_DEFAUT, "sans pouvoir prédictif"
        else:
            poids = max(0.0, min(POIDS_MAX, ecart / R_REFERENCE))
            verdict = "discriminante"
        out[code] = PoidsFigure(code, round(poids, 3), n, round(r_pres, 3),
                                round(r_abs, 3), verdict)
    return out


def mesurer_bruit(n_essais: int = 2000, n_bougies: int = 80,
                  graine: int = 0) -> dict:
    """Re-mesure le taux d'apparition de chaque figure sur du bruit pur.

    À relancer si les seuils de détection changent : `TAUX_SUR_BRUIT` doit
    rester à jour, sinon la référence ment. C'est le seul chiffre du module
    qu'on ne peut pas se permettre de laisser vieillir.
    """
    import random
    from collections import Counter
    cpt, avec, total = Counter(), 0, 0
    for g in range(n_essais):
        rng = random.Random(graine + g)
        bs, px = [], 100.0
        for _ in range(n_bougies):
            px *= (1 + rng.gauss(0, 0.006))
            o = px * (1 + rng.uniform(-.0015, .0015))
            bs.append({"open": o, "high": max(o, px) * (1 + abs(rng.gauss(0, .002))),
                       "low": min(o, px) * (1 - abs(rng.gauss(0, .002))),
                       "close": px})
        fs = detecter(bs)
        avec += bool(fs); total += len(fs)
        for f in fs:
            cpt[f.code] += 1
    return {"au_moins_une": avec / n_essais, "par_graphique": total / n_essais,
            "taux": {k: round(v / n_essais, 4) for k, v in cpt.most_common()}}


def rapport(poids: dict[str, PoidsFigure]) -> str:
    if not poids:
        return "# Figures\n\nAucune figure observée — rien à calibrer.\n"
    l = ["# Ce que valent les figures SUR TON JOURNAL", "",
         f"> **{AU_MOINS_UNE_SUR_BRUIT:.0%} des graphiques PUREMENT ALÉATOIRES "
         f"contiennent au moins une figure.** Mesuré sur 2 000 marches au "
         f"hasard. La colonne « bruit » ci-dessous dit à quelle fréquence "
         f"chaque figure apparaît sans qu'il se passe quoi que ce soit.", "",
         "| figure | n | bruit | R présente | R absente | poids | verdict |",
         "|---|---:|---:|---:|---:|---:|---|"]
    for f in sorted(poids.values(), key=lambda x: (-x.poids, -x.n)):
        bruit = TAUX_SUR_BRUIT.get(f.code)
        bt = f"{bruit:.0%}" if bruit is not None else "—"
        l.append(f"| `{f.code}` | {f.n} | {bt} | {f.r_present:+.2f} "
                 f"| {f.r_absent:+.2f} | {f.poids:.2f} | {f.verdict} |")
    utiles = [f for f in poids.values() if f.poids > 0]
    l += ["", f"**{len(utiles)} figure(s) discriminante(s)** sur {len(poids)} "
              f"observées."]
    if not utiles:
        l += ["", "> Aucune figure ne bat le bruit sur ce journal. C'est le "
                  "résultat attendu au vu de la littérature — et c'est une "
                  "information, pas un échec du module. Tant que cette ligne "
                  "reste vraie, **les figures n'influencent aucune décision**."]
    inverses = [f.code for f in poids.values() if "retourner" in f.verdict]
    if inverses:
        l += ["", f"> ⚠️ **À retourner** : {', '.join(inverses)}. Elles "
                  f"précèdent l'inverse de ce qu'elles annoncent — donc elles "
                  f"portent de l'information, à condition de l'inverser."]
    return "\n".join(l) + "\n"


# --------------------------------------------------------------------------
def _demo() -> None:
    import math, random
    rng = random.Random(11)

    def serie(f):
        bs, px = [], 100.0
        for i in range(80):
            px = f(i, px)
            o = px * (1 + rng.uniform(-.0015, .0015))
            h = max(o, px) * (1 + abs(rng.gauss(0, .002)))
            b = min(o, px) * (1 - abs(rng.gauss(0, .002)))
            bs.append({"open": o, "high": h, "low": b, "close": px})
        return bs

    cas = [
        ("Triangle ascendant — résistance plate, creux qui montent",
         serie(lambda i, p: 100 + min(4.0, i * .07) * (1 if i % 8 < 4 else .2)
               + math.sin(i / 2) * max(.2, 2 - i * .022))),
        ("Rectangle — bloqué entre deux niveaux",
         serie(lambda i, p: 100 + math.sin(i / 3) * 2)),
        ("Marché sans figure — bruit pur",
         serie(lambda i, p: p * (1 + rng.gauss(0, .006)))),
    ]
    for titre, bs in cas:
        fs = detecter(bs)
        print(f"\n{'=' * 70}\n  {titre}\n{'=' * 70}")
        for f in fs:
            print("   ", f)
        if not fs:
            print("    aucune figure — et c'est un résultat")
        b = biais(fs)
        print(f"    → biais {b['sens']} ({b['score']:+.2f}) · {b['motif']}")

    print(f"\n{'=' * 70}\n  CALIBRATION — figure utile contre figure décorative\n{'=' * 70}")
    paires = []
    for i in range(300):
        marteau = i % 3 == 0
        doji = i % 4 == 0
        gagne = rng.random() < (0.55 if marteau else 0.20)
        figs = ([Figure("marteau", "bougie", "haussier", 0, 0, 1.0)] if marteau else []) \
             + ([Figure("doji", "bougie", "indetermine", 0, 0, 1.0)] if doji else [])
        paires.append(({"statut": "TP" if gagne else "SL",
                        "r_realise": 2.1 if gagne else -1.0}, figs))
    print(rapport(calibrer(paires)))


if __name__ == "__main__":
    _demo()
