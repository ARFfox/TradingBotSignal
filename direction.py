#!/usr/bin/env python3
"""
AG-19 DIRECTEUR — la direction du marché, décidée sur TOUTES les sources.

    python3 direction.py        # démonstration

Ce que fait ce module
---------------------
Il rassemble ce que disent tous les agents — structure, marché, intermarché,
figures chartistes, momentum, mémoire du superviseur — et rend **une seule
direction**, avec le raisonnement écrit en français.

Les quatre règles qui l'empêchent d'être une girouette
-------------------------------------------------------
1. **« INDÉTERMINÉE » est une réponse.** Un module qui trouve toujours une
   direction n'en trouve aucune : sa sortie est connue d'avance. Sur des
   sources qui se contredisent ou une base trop mince, il dit qu'il ne sait
   pas, et c'est le comportement recherché. C'est testé.

2. **Une famille d'information = une voix.** « le marché monte », « le régime
   est haussier » et « l'instrument mène son marché haussier » sont une seule
   observation vue trois fois. Les additionner fabrique une unanimité qui
   n'existe pas — le défaut qui avait produit « 16 sur 16, score +1,00 ».

3. **DÉCRIRE et PRÉDIRE n'ont pas le même poids par défaut.**
   · Une source DESCRIPTIVE constate ce qui EST : « le prix est 3,2 % au-dessus
     de sa moyenne à 50 ». C'est un fait — poids 1,0 en attendant mieux.
   · Une source PRÉDICTIVE affirme ce qui VA ÊTRE : « ce triangle annonce une
     hausse ». La littérature dit majoritairement « pas d'edge » — poids 0,0
     tant que ce n'est pas mesuré sur TON journal.
   Les deux finissent avec un poids mesuré. Le défaut n'est que le point de
   départ, et il n'est pas le même.

4. **La certitude vient de l'ACCORD ET DE LA BASE, jamais de la force.**
   Cinq sources faibles qui disent la même chose valent mieux qu'une source
   forte et seule. Et cinq sources d'accord dont aucune n'est mesurée ne
   valent rien du tout.

Sur « qu'il analyse comme un humain »
--------------------------------------
Un bon analyste humain ne se reconnaît pas à sa confiance : il se reconnaît
à trois choses, et le module les fait toutes les trois.

  · il NOMME ses chiffres au lieu de dire « le marché semble haussier » ;
  · il DIT QUAND IL NE SAIT PAS, au lieu de meubler ;
  · il SAIT CE QUI LE FERAIT CHANGER D'AVIS, et le dit avant l'événement.

C'est `expliquer()`. Un texte fluide et sûr de lui est facile à écrire et ne
vaut rien — ce qui compte est qu'il soit réfutable.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from statistiques import wilson

# --------------------------------------------------------------------------
N_MIN_SOURCE = 30        # résolus avant qu'une source ait un poids mesuré
Z_BRUIT = 1.64
R_REFERENCE = 0.50
POIDS_MAX = 2.0
PLAFOND_R = 10.0

SEUIL_SENS = 0.18        # sous ce score absolu : indéterminée
SEUIL_FRANC = 0.50       # au-dessus : direction franche
BASE_MINIMALE = 2.0      # somme des poids sous laquelle rien n'est affirmé
ACCORD_MINIMAL = 0.60    # part des familles qui doivent aller dans le sens

# Familles d'information. Deux sources de la même famille ne votent qu'une fois.
FAMILLES = ("tendance", "marche", "intermarche", "figure", "momentum", "memoire")


@dataclass
class Source:
    """Ce qu'un agent apporte au débat sur la direction."""
    code: str
    famille: str
    sens: str            # "haussier" | "baissier" | "neutre"
    force: float         # 0..1 — intensité du FAIT, pas une confiance
    mesure: str          # le chiffre qui le fonde, en clair
    predictive: bool = False   # True = elle affirme l'avenir → poids 0 par défaut
    agent: str = ""

    @property
    def poids_defaut(self) -> float:
        return 0.0 if self.predictive else 1.0


@dataclass
class Direction:
    sens: str                    # haussier | baissier | INDÉTERMINÉE
    score: float                 # −1..+1
    certitude: float             # 0..1 — accord × base, jamais la force seule
    base: float                  # somme des poids effectifs
    accord: float                # part des familles dans le sens majoritaire
    sources: list = field(default_factory=list)
    pour: list = field(default_factory=list)
    contre: list = field(default_factory=list)
    n_mesurees: int = 0
    motif: str = ""
    bascule: str = ""            # la source dont le retournement suffirait

    @property
    def franche(self) -> bool:
        return self.sens != "INDÉTERMINÉE" and abs(self.score) >= SEUIL_FRANC


# ==========================================================================
# 1. CONSTRUIRE LES SOURCES À PARTIR DES AGENTS
# ==========================================================================
def sources_depuis_agents(structure=None, marche=None, intermarche=None,
                          figures_biais=None, momentum=None,
                          memoire=None) -> list[Source]:
    """Traduit les sorties des agents existants en sources comparables.

    Chaque argument est optionnel : une source absente ne vote pas, elle ne
    vote pas « neutre ». La différence compte — un agent muet doit réduire la
    base, pas diluer le score.
    """
    out: list[Source] = []

    # --- AG-02 Structure : DESCRIPTIF (où est le prix par rapport à sa moyenne)
    if structure and structure.get("ecart_ema") is not None:
        e = float(structure["ecart_ema"])
        out.append(Source(
            "structure_ema", "tendance",
            "haussier" if e > 0 else "baissier" if e < 0 else "neutre",
            min(1.0, abs(e) / 0.03),
            f"prix {e:+.2%} vs EMA50", predictive=False, agent="AG-02"))

    # --- AG-11..14 Marché : DESCRIPTIF (le régime mesuré du marché)
    if marche and marche.get("regime") in ("haussier", "baissier", "neutre"):
        out.append(Source(
            "regime_marche", "marche", marche["regime"],
            min(1.0, float(marche.get("largeur", 0.5))),
            f"{marche.get('nom', 'marché')} {marche['regime']} · "
            f"largeur {float(marche.get('largeur', 0)):.0%}",
            predictive=False, agent="AG-11..14"))

    # --- AG-10 Miroir : DESCRIPTIF (ce que font les actifs corrélés)
    if intermarche and intermarche.get("score") is not None:
        s = float(intermarche["score"])
        fiable = bool(intermarche.get("fiable", False))
        out.append(Source(
            "miroir", "intermarche",
            "haussier" if s > 0 else "baissier" if s < 0 else "neutre",
            min(1.0, abs(s)) * (1.0 if fiable else 0.4),
            f"score intermarché {s:+.2f}"
            + ("" if fiable else " · base faible, force réduite"),
            predictive=False, agent="AG-10"))

    # --- figures.py : PRÉDICTIF → poids 0 par défaut
    if figures_biais and figures_biais.get("sens"):
        n = int(figures_biais.get("n_figures", 0))
        attendu = float(figures_biais.get("attendu_sur_bruit", 0))
        out.append(Source(
            "figures", "figure", figures_biais["sens"],
            min(1.0, abs(float(figures_biais.get("score", 0)))),
            f"{n} figure(s) · le bruit en donnerait {attendu:.1f}",
            predictive=True, agent="AG-19"))

    # --- momentum : DESCRIPTIF
    if momentum and momentum.get("rsi") is not None:
        r = float(momentum["rsi"])
        out.append(Source(
            "rsi", "momentum",
            "haussier" if r > 55 else "baissier" if r < 45 else "neutre",
            min(1.0, abs(r - 50) / 25), f"RSI {r:.1f}",
            predictive=False, agent="AG-02"))

    # --- mémoire du superviseur : DESCRIPTIF (ce qui a été mesuré ici)
    if memoire and memoire.get("esperance") is not None \
            and int(memoire.get("n", 0)) >= N_MIN_SOURCE:
        e = float(memoire["esperance"]); n = int(memoire["n"])
        sens = memoire.get("sens_favorable", "neutre")
        out.append(Source(
            "historique_couple", "memoire",
            sens if e > 0 else "neutre",
            min(1.0, abs(e)), f"{e:+.2f}R mesuré sur {n} signaux",
            predictive=False, agent="AG-00"))
    return out


# ==========================================================================
# 2. LA DÉCISION
# ==========================================================================
def decider(sources: list[Source], poids: dict[str, float] | None = None) -> Direction:
    """La direction, ou l'aveu qu'il n'y en a pas."""
    p = poids or {}
    if not sources:
        return Direction("INDÉTERMINÉE", 0.0, 0.0, 0.0, 0.0,
                         motif="aucun agent n'a répondu")

    # Une famille = une voix, celle de son membre le plus fort.
    par_famille: dict[str, Source] = {}
    effectif: dict[str, float] = {}
    for s in sources:
        w = p.get(s.code, s.poids_defaut) * s.force
        if w <= 0:
            continue
        if s.famille not in effectif or w > effectif[s.famille]:
            effectif[s.famille], par_famille[s.famille] = w, s

    if not effectif:
        n_pred = sum(1 for s in sources if s.predictive)
        return Direction(
            "INDÉTERMINÉE", 0.0, 0.0, 0.0, 0.0, sources=sources,
            motif=(f"{'la source disponible est' if len(sources)==1 else f'les {len(sources)} sources disponibles sont'} soit "
                   f"neutre(s), soit non mesurée(s)"
                   + (f" ({n_pred} prédictive(s) au poids zéro)" if n_pred else "")))

    haut = sum(w for f, w in effectif.items() if par_famille[f].sens == "haussier")
    bas = sum(w for f, w in effectif.items() if par_famille[f].sens == "baissier")
    base = sum(effectif.values())
    brut = haut - bas
    score = max(-1.0, min(1.0, brut / (1.0 + abs(brut))))

    total_direction = haut + bas
    accord = (max(haut, bas) / total_direction) if total_direction > 0 else 0.0
    n_mes = sum(1 for f in par_famille.values() if p.get(f.code, 0.0) > 0)

    pour = [s for f, s in par_famille.items()
            if s.sens == ("haussier" if brut > 0 else "baissier") and s.sens != "neutre"]
    contre = [s for f, s in par_famille.items()
              if s.sens == ("baissier" if brut > 0 else "haussier") and s.sens != "neutre"]

    # --- les trois raisons de ne pas se prononcer ------------------------
    if base < BASE_MINIMALE:
        return Direction("INDÉTERMINÉE", round(score, 3), 0.0, round(base, 2),
                         round(accord, 2), sources, pour, contre, n_mes,
                         f"base d'information trop mince ({base:.1f} < "
                         f"{BASE_MINIMALE}) — {len(effectif)} famille(s) seulement")
    if accord < ACCORD_MINIMAL:
        return Direction("INDÉTERMINÉE", round(score, 3), 0.0, round(base, 2),
                         round(accord, 2), sources, pour, contre, n_mes,
                         f"les sources se contredisent ({accord:.0%} d'accord, "
                         f"{ACCORD_MINIMAL:.0%} exigés)")
    if abs(score) < SEUIL_SENS:
        return Direction("INDÉTERMINÉE", round(score, 3), 0.0, round(base, 2),
                         round(accord, 2), sources, pour, contre, n_mes,
                         f"score {score:+.2f} sous le seuil — aucun sens ne domine")

    # La certitude ne vient JAMAIS de la force seule : accord × base × mesure.
    part_mesuree = n_mes / len(effectif)
    certitude = accord * min(1.0, base / 4.0) * (0.4 + 0.6 * part_mesuree)
    sens = "haussier" if score > 0 else "baissier"
    return Direction(sens, round(score, 3), round(certitude, 3), round(base, 2),
                     round(accord, 2), sources, pour, contre, n_mes,
                     f"{len(pour)} famille(s) pour, {len(contre)} contre · "
                     f"{n_mes}/{len(effectif)} au poids mesuré",
                     bascule=_bascule(effectif, par_famille, sens))


def _bascule(effectif: dict, par_famille: dict, sens: str) -> str:
    """La PLUS PETITE source dont le retournement casserait le verdict.

    Lister « que la tendance ou le marché ou le momentum change d'avis » ne
    sert à rien : c'est vrai de toute conclusion. Ce qui est utile, et ce
    qu'un analyste dit vraiment, c'est LE point faible — la source dont le
    retournement suffit à lui seul. On le calcule en retournant chaque
    famille et en regardant si le verdict tient encore.
    """
    def verdict(eff, fam):
        h = sum(w for f, w in eff.items() if fam[f] == "haussier")
        b = sum(w for f, w in eff.items() if fam[f] == "baissier")
        brut = h - b
        sc = max(-1.0, min(1.0, brut / (1.0 + abs(brut))))
        tot = h + b
        acc = (max(h, b) / tot) if tot else 0.0
        if sum(eff.values()) < BASE_MINIMALE or acc < ACCORD_MINIMAL \
                or abs(sc) < SEUIL_SENS:
            return "INDÉTERMINÉE"
        return "haussier" if sc > 0 else "baissier"

    sens_actuel = {f: s.sens for f, s in par_famille.items()}
    inverse = {"haussier": "baissier", "baissier": "haussier", "neutre": "neutre"}
    fragiles = []
    for f in effectif:
        if sens_actuel[f] != sens:
            continue
        essai = dict(sens_actuel)
        essai[f] = inverse[essai[f]]
        if verdict(effectif, essai) != sens:
            fragiles.append((effectif[f], f, par_famille[f]))

    if not fragiles:
        n = len(effectif)
        return (f"aucune source seule ne suffit — il en faudrait au moins deux "
                f"sur {n} pour renverser le verdict. C'est ce qui rend cette "
                f"direction solide, plus que son score.")
    fragiles.sort()
    poids, fam, src = fragiles[0]
    return (f"que **{src.code}** ({src.mesure}) passe "
            f"{inverse[src.sens]} — à lui seul, il ferait basculer le verdict. "
            f"C'est le point faible de cette analyse, et il pèse {poids:.1f} "
            f"sur {sum(effectif.values()):.1f}.")


# ==========================================================================
# 3. LE RAISONNEMENT ÉCRIT
# ==========================================================================
def expliquer(d: Direction) -> str:
    """Le raisonnement, en français, avec les chiffres et les objections.

    ⚠️ Ce texte n'a pas le droit d'être plus sûr que `d.certitude`. Un
    paragraphe fluide et affirmatif est facile à produire et ne vaut rien :
    ce qui rend une analyse utile est qu'elle soit RÉFUTABLE.
    """
    l = []
    if d.sens == "INDÉTERMINÉE":
        l.append(f"**Direction indéterminée.** {d.motif.capitalize()}.")
        if d.pour and d.contre:
            l.append("")
            l.append(f"Ce qui pousse à la hausse : "
                     + " · ".join(f"{s.mesure}" for s in d.pour[:3]) + ".")
            l.append(f"Ce qui pousse à la baisse : "
                     + " · ".join(f"{s.mesure}" for s in d.contre[:3]) + ".")
            l.append("")
            l.append("Les deux camps tiennent des faits réels. Ce n'est pas un "
                     "manque d'analyse, c'est un marché sans direction — et "
                     "prendre position dessus revient à jouer à pile ou face.")
        return "\n".join(l) + "\n"

    mot = "franchement " if d.franche else "modérément "
    l.append(f"**Marché {mot}{d.sens}** — score {d.score:+.2f}, "
             f"certitude {d.certitude:.0%}.")
    l.append("")
    l.append("Ce qui le dit :")
    for s in sorted(d.pour, key=lambda x: -x.force):
        l.append(f"- {s.mesure} *({s.agent or s.code})*")

    if d.contre:
        l.append("")
        l.append("Ce qui s'y oppose, et qu'il ne faut pas effacer :")
        for s in sorted(d.contre, key=lambda x: -x.force):
            l.append(f"- {s.mesure} *({s.agent or s.code})*")

    l.append("")
    l.append(f"**Ce qui me ferait changer d'avis :** {d.bascule}")

    if d.n_mesurees == 0:
        l.append("")
        l.append("> ⚠️ **Aucune de ces sources n'a encore de poids mesuré sur "
                 "ton journal.** Elles décrivent correctement ce que fait le "
                 "marché ; rien ne prouve encore qu'elles précèdent un gain. "
                 "La certitude affichée en tient compte — elle est plafonnée "
                 "à 40 % tant que c'est le cas.")
    elif d.n_mesurees < len(d.pour) + len(d.contre):
        l.append("")
        l.append(f"> {d.n_mesurees} source(s) sur "
                 f"{len(d.pour) + len(d.contre)} portent un poids mesuré. "
                 f"Les autres comptent pour ce qu'elles décrivent, pas pour "
                 f"ce qu'elles prédisent.")
    return "\n".join(l) + "\n"


# ==========================================================================
# 4. CALIBRATION — chaque source gagne son poids
# ==========================================================================
@dataclass
class PoidsSource:
    code: str
    poids: float
    n: int
    r_accord: float      # R moyen quand la source était d'accord avec le signal
    r_desaccord: float
    verdict: str


def calibrer(paires) -> dict[str, PoidsSource]:
    """`paires` : liste de (signal résolu, [sources actives à l'émission]).

    Mesure la DISCRIMINATION : le R quand la source était d'accord avec le
    sens du signal, contre le R quand elle le contredisait. Une source qui
    donne le même R dans les deux cas ne sert à rien, aussi juste soit son
    analyse — elle décrit sans prédire.
    """
    acc: dict[str, list[float]] = defaultdict(list)
    des: dict[str, list[float]] = defaultdict(list)

    for s, srcs in paires:
        st = s.get("statut") if isinstance(s, dict) else getattr(s, "statut", None)
        if st not in ("TP", "SL"):
            continue
        r = s.get("r_realise") if isinstance(s, dict) else getattr(s, "r_realise", None)
        if r is None:
            continue
        r = max(-PLAFOND_R, min(PLAFOND_R, float(r)))
        sens_signal = (s.get("sens") if isinstance(s, dict)
                       else getattr(s, "sens", "")) or ""
        attendu = "haussier" if sens_signal == "achat" else "baissier"
        for src in srcs:
            code = src.code if isinstance(src, Source) else str(src)
            sens = getattr(src, "sens", "neutre")
            if sens == "neutre":
                continue
            (acc if sens == attendu else des)[code].append(r)

    out: dict[str, PoidsSource] = {}
    for code in set(acc) | set(des):
        a, d_ = acc[code], des[code]
        n = len(a) + len(d_)
        ra = sum(a) / len(a) if a else 0.0
        rd = sum(d_) / len(d_) if d_ else 0.0
        ecart = ra - rd

        va = (sum(x * x for x in a) / len(a) - ra ** 2) if len(a) > 1 else 0.0
        vd = (sum(x * x for x in d_) / len(d_) - rd ** 2) if len(d_) > 1 else 0.0
        marge = Z_BRUIT * (max(0.0, va) / max(len(a), 1)
                           + max(0.0, vd) / max(len(d_), 1)) ** 0.5

        if n < N_MIN_SOURCE or not a or not d_:
            poids, verdict = 0.0, f"non mesurée ({n}/{N_MIN_SOURCE})"
        elif ecart <= -marge:
            poids, verdict = 0.0, "à retourner — elle prédit l'inverse"
        elif ecart <= marge:
            poids, verdict = 0.0, "décrit sans prédire"
        else:
            poids = max(0.0, min(POIDS_MAX, ecart / R_REFERENCE))
            verdict = "discriminante"
        out[code] = PoidsSource(code, round(poids, 3), n, round(ra, 3),
                                round(rd, 3), verdict)
    return out


def rapport(poids: dict[str, PoidsSource]) -> str:
    if not poids:
        return "# Direction\n\nAucune source observée — rien à calibrer.\n"
    l = ["# Ce que vaut chaque source de direction", "",
         "| source | n | R si d'accord | R si contre | poids | verdict |",
         "|---|---:|---:|---:|---:|---|"]
    for s in sorted(poids.values(), key=lambda x: (-x.poids, -x.n)):
        l.append(f"| `{s.code}` | {s.n} | {s.r_accord:+.2f} | "
                 f"{s.r_desaccord:+.2f} | {s.poids:.2f} | {s.verdict} |")
    utiles = [s for s in poids.values() if s.poids > 0]
    l += ["", f"**{len(utiles)} source(s) discriminante(s)** sur {len(poids)}."]
    if not utiles:
        l += ["", "> Aucune source ne prédit mieux que le bruit sur ce journal. "
                  "Le Directeur continue de décrire le marché — il ne "
                  "prétend pas le prévoir, et sa certitude reste plafonnée."]
    return "\n".join(l) + "\n"


# --------------------------------------------------------------------------
def _demo() -> None:
    cas = [
        ("Tout concorde, et c'est mesuré",
         dict(structure={"ecart_ema": 0.031},
              marche={"regime": "haussier", "largeur": 0.78, "nom": "matières"},
              intermarche={"score": 0.52, "fiable": True},
              figures_biais={"sens": "haussier", "score": 0.4, "n_figures": 2,
                             "attendu_sur_bruit": 0.5},
              momentum={"rsi": 62.0},
              memoire={"esperance": 0.22, "n": 41, "sens_favorable": "haussier"}),
         {"structure_ema": 1.4, "regime_marche": 1.1, "miroir": 0.9}),

        ("Les sources se contredisent",
         dict(structure={"ecart_ema": 0.028},
              marche={"regime": "baissier", "largeur": 0.71, "nom": "forex"},
              intermarche={"score": -0.45, "fiable": True},
              momentum={"rsi": 58.0}),
         {"structure_ema": 1.2, "regime_marche": 1.2, "miroir": 1.0}),

        ("Seulement des figures — rien de mesuré",
         dict(figures_biais={"sens": "haussier", "score": 0.8, "n_figures": 3,
                             "attendu_sur_bruit": 1.7}),
         {}),

        ("Marché calme, tout est neutre",
         dict(structure={"ecart_ema": 0.001},
              marche={"regime": "neutre", "largeur": 0.2, "nom": "actions"},
              intermarche={"score": 0.04, "fiable": True},
              momentum={"rsi": 51.0}),
         {"structure_ema": 1.0, "regime_marche": 1.0}),
    ]
    for titre, kw, poids in cas:
        d = decider(sources_depuis_agents(**kw), poids)
        print(f"\n{'=' * 74}\n  {titre}\n{'=' * 74}")
        print(f"  base {d.base:.1f} · accord {d.accord:.0%} · "
              f"{d.n_mesurees} source(s) mesurée(s)\n")
        print(expliquer(d))


if __name__ == "__main__":
    _demo()
