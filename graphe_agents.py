#!/usr/bin/env python3
"""
AG-20 GRAPHE — la carte vivante du système.

    python3 graphe_agents.py       # demonstration

Construit les noeuds et les liens de la vue en graphe (style Obsidian).

Le principe qui rend ce graphe utile
------------------------------------
Un schema d'architecture ou "l'agent A est relie a l'agent B" est une
decoration : il est identique quand le systeme va bien et quand il va mal.
Ici, TOUT ce qui est visible est mesure a l'instant du rendu :

  taille du noeud    = conviction reelle de l'agent
  halo du noeud      = son statut (actif, veille, panne)
  epaisseur du lien  = force de la relation mesuree
  couleur du lien    = confirme / contredit / neutre EN CE MOMENT
  fleche             = avance mesuree d'un marche sur un autre

Un lien qui passe du vert au rouge signale un desaccord entre deux agents.
Un noeud qui retrecit signale un agent qui perd confiance. Un noeud gris
signale un agent mort. Le graphe se lit d'un coup d'oeil, et c'est le seul
interet d'une vue en graphe : voir en 1 seconde ce qu'un tableau demande
30 secondes a lire.

Aucun appel reseau. On injecte l'etat, il produit le graphe.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

# --------------------------------------------------------------------------
# Les agents. C'est une DONNEE : ajouter un agent ne demande aucun code.
#   couche : ou il se situe dans la chaine de decision
#   ecoute : de qui il recoit
# --------------------------------------------------------------------------
AGENTS: dict[str, dict] = {
    # --- couche perception : ils lisent le monde -------------------------
    "AG-01": {"nom": "Vigie", "emoji": "📡", "couche": "perception",
              "coul": "#58a6ff", "ecoute": []},
    "AG-02": {"nom": "Structure", "emoji": "📈", "couche": "perception",
              "coul": "#3fb950", "ecoute": []},
    "AG-04": {"nom": "Traceur", "emoji": "✏️", "couche": "perception",
              "coul": "#a371f7", "ecoute": ["AG-02"]},
    "AG-05": {"nom": "Minières & Flux", "emoji": "⛏️", "couche": "perception",
              "coul": "#ff7b72", "ecoute": []},
    # --- couche marches : un par univers ---------------------------------
    "AG-11": {"nom": "Forex", "emoji": "💱", "couche": "marche",
              "coul": "#58a6ff", "ecoute": ["AG-02"]},
    "AG-12": {"nom": "Crypto", "emoji": "🪙", "couche": "marche",
              "coul": "#f0b90b", "ecoute": ["AG-02"]},
    "AG-13": {"nom": "Matières", "emoji": "🥇", "couche": "marche",
              "coul": "#e3b341", "ecoute": ["AG-02"]},
    "AG-14": {"nom": "Actions", "emoji": "📊", "couche": "marche",
              "coul": "#3fb950", "ecoute": ["AG-02"]},
    # --- couche relations : elles relient les marches entre eux ----------
    "AG-09": {"nom": "Constellation", "emoji": "🌐", "couche": "relation",
              "coul": "#a371f7", "ecoute": ["AG-11", "AG-12", "AG-13", "AG-14"]},
    "AG-15": {"nom": "Intermarchés", "emoji": "🕸️", "couche": "relation",
              "coul": "#f778ba", "ecoute": ["AG-11", "AG-12", "AG-13", "AG-14"]},
    "AG-10": {"nom": "Miroir", "emoji": "🪞", "couche": "relation",
              "coul": "#f778ba", "ecoute": ["AG-09", "AG-02"]},
    # --- couche critique : ils s'opposent --------------------------------
    # Deux avocats, pas un. Un systeme qui n'a qu'un contradicteur apprend a
    # se mefier de tout ; un systeme qui n'a qu'un defenseur apprend a tout
    # justifier. Dans les deux cas la conclusion est connue d'avance.
    "AG-16": {"nom": "Avocat du diable", "emoji": "😈", "couche": "critique",
              "coul": "#f85149", "ecoute": ["AG-03", "AG-01", "AG-10"]},
    "AG-18": {"nom": "Avocat de la défense", "emoji": "🛡️", "couche": "critique",
              "coul": "#3fb950", "ecoute": ["AG-03", "AG-02", "AG-09"]},
    # --- couche decision -------------------------------------------------
    "AG-03": {"nom": "Stratège", "emoji": "♟️", "couche": "decision",
              "coul": "#e3b341", "ecoute": ["AG-02", "AG-04", "AG-05"]},
    "AG-00": {"nom": "Superviseur", "emoji": "🧠", "couche": "chef",
              "coul": "#1f6feb",
              "ecoute": ["AG-01", "AG-02", "AG-03", "AG-04", "AG-05",
                         "AG-09", "AG-10", "AG-11", "AG-12", "AG-13",
                         "AG-14", "AG-15", "AG-16", "AG-18"]},
    # --- sorties ---------------------------------------------------------
    "OUT-1": {"nom": "Notification", "emoji": "🔔", "couche": "sortie",
              "coul": "#7ee787", "ecoute": ["AG-00"]},
    "OUT-2": {"nom": "Toi — décision", "emoji": "👤", "couche": "sortie",
              "coul": "#e6edf3", "ecoute": ["OUT-1"]},
}

COUCHES = ["perception", "marche", "relation", "critique", "decision",
           "chef", "sortie"]

# Un lien n'apparait que s'il porte une information.
SEUIL_LIEN = 0.15

# Les trois positions affichables et leur couleur de halo.
#   pour    = cet agent soutient le signal en cours
#   contre  = il s'y oppose
#   neutre  = il n'a rien trouve a dire. C'EST UNE INFORMATION, pas un vide :
#             un agent qui est "pour" a chaque signal ne vote pas, il applaudit.
POSITIONS = {"pour": "#3fb950", "contre": "#f85149", "neutre": "#6e7681"}


@dataclass
class Noeud:
    id: str
    nom: str
    emoji: str
    couche: str
    coul: str
    taille: float = 1.0          # derive de la conviction
    conviction: int = 50
    statut: str = "INCONNU"
    vivant: bool = True
    detail: str = ""
    # Position PRISE sur le signal en cours : "pour" | "contre" | "neutre".
    # C'est la seule chose du graphe qui change d'une seconde a l'autre sans
    # qu'aucune correlation ne bouge — donc la seule qui dise ce que le
    # systeme est en train de PENSER, et pas seulement comment il est cable.
    position: str = "neutre"


@dataclass
class Lien:
    de: str
    vers: str
    type: str                    # alimente | confirme | contredit | bloque | correlation
    poids: float = 0.5           # epaisseur
    etiquette: str = ""
    jours: int = 0               # avance mesuree, 0 = simultane


@dataclass
class Graphe:
    noeuds: list[Noeud] = field(default_factory=list)
    liens: list[Lien] = field(default_factory=list)

    def json(self) -> dict:
        return {"noeuds": [asdict(n) for n in self.noeuds],
                "liens": [asdict(l) for l in self.liens],
                "couches": COUCHES}

    def resume(self) -> str:
        morts = [n.id for n in self.noeuds if not n.vivant]
        conflits = [l for l in self.liens if l.type in ("contredit", "bloque")]
        return (f"{len(self.noeuds)} nœuds · {len(self.liens)} liens · "
                f"{len(conflits)} conflit(s) · {self.balance()}"
                + (f" · {len(morts)} agent(s) muet(s) : {', '.join(morts)}" if morts else ""))

    def balance(self) -> str:
        """Le decompte pour / contre / neutre, en une ligne.

        A lire avec mefiance : si ce decompte ne bouge jamais d'un signal
        a l'autre, les agents ne votent pas, ils recitent.
        """
        c = {p: sum(1 for n in self.noeuds if n.position == p and n.vivant
                    and n.couche not in ("sortie",))
             for p in POSITIONS}
        return f"{c['pour']} pour · {c['contre']} contre · {c['neutre']} neutre"


# --------------------------------------------------------------------------
def position_de(carte: dict) -> str:
    """Quelle position cet agent prend-il sur le signal en cours ?

    Ordre de lecture : d'abord ce que l'agent DIT ("position"), sinon ce
    qu'on peut deduire de son avis. On ne devine JAMAIS a partir de la
    conviction seule : une conviction de 90 % sur "le marche est baissier"
    est une position CONTRE un achat, et POUR une vente. Confondre les deux
    afficherait exactement l'inverse de la verite.
    """
    p = str(carte.get("position", "")).lower()
    if p in POSITIONS:
        return p
    avis = str(carte.get("avis", "")).lower()
    if avis in ("pour", "confirme", "favorable"):
        return "pour"
    if avis in ("contre", "contredit", "defavorable", "bloque"):
        return "contre"
    return "neutre"


def construire(cartes: list[dict] | None = None,
               intermarches: dict | None = None,
               miroir: dict | None = None,
               avocat: dict | None = None,
               defense: dict | None = None) -> Graphe:
    """Assemble le graphe a partir de l'etat reel.

    cartes       : les cartes d'agent du panneau (code, statut, conviction…)
    intermarches : sortie de MatriceMarches.graphe()
    miroir       : ScoreIntermarche serialise (confirment, contredisent, bloque)
    avocat       : AG-16 — {"cible": "AG-03", "objections": [...], "bloque": bool}
    defense      : AG-18 — {"cible": "AG-03", "arguments": [...]}
                   Les deux acceptent directement un Verdict d'avocats.py
                   serialise : voir `depuis_verdict()`.

    Tous les arguments sont optionnels : un graphe partiel vaut mieux qu'une
    exception. Un agent sans carte s'affiche en gris "muet" — ce qui est
    exactement l'information qu'on veut voir.
    """
    par_code = {c.get("code"): c for c in (cartes or []) if c.get("code")}
    g = Graphe()

    # --- noeuds ---------------------------------------------------------
    for code, a in AGENTS.items():
        c = par_code.get(code)
        if c:
            conv = int(c.get("conviction", 50))
            statut = str(c.get("statut", "?"))
            vivant = statut not in ("PANNE", "MUET", "INITIALISATION")
            detail = (c.get("activites") or [""])[0][:80]
        else:
            conv, statut, vivant, detail = 50, "MUET", False, "aucune donnée"
        pos = position_de(c) if c else "neutre"
        if a["couche"] == "sortie":
            conv, statut, vivant, pos = 100, "—", True, "neutre"

        g.noeuds.append(Noeud(
            id=code, nom=a["nom"], emoji=a["emoji"], couche=a["couche"],
            coul=a["coul"] if vivant else "#484f58",
            # Rayon en racine de la conviction : une conviction de 100 ne
            # doit pas ecraser visuellement une conviction de 50.
            taille=round(0.6 + 0.9 * (conv / 100) ** 0.5, 3),
            conviction=conv, statut=statut, vivant=vivant, detail=detail,
            position=pos))

    # --- liens d'alimentation (la chaine de decision) -------------------
    for code, a in AGENTS.items():
        for source in a["ecoute"]:
            if source in AGENTS:
                g.liens.append(Lien(de=source, vers=code, type="alimente",
                                    poids=0.25))

    # --- liens de correlation entre marches ------------------------------
    cle_marche = {"forex": "AG-11", "crypto": "AG-12",
                  "matieres": "AG-13", "actions": "AG-14"}
    for l in (intermarches or {}).get("liens", []):
        a, b = cle_marche.get(l.get("de")), cle_marche.get(l.get("vers"))
        if not a or not b:
            continue
        corr = float(l.get("corr", 0.0))
        if abs(corr) < SEUIL_LIEN:
            continue
        meneur = cle_marche.get(l.get("meneur"))
        jours = int(l.get("jours", 0) or 0)
        # La fleche part du MENEUR : c'est lui qui informe l'autre.
        de, vers = (meneur, b if meneur == a else a) if (meneur and jours) else (a, b)
        g.liens.append(Lien(de=de, vers=vers, type="correlation",
                            poids=round(abs(corr), 3), jours=jours,
                            etiquette=f"{corr:+.2f}" +
                                      (f" · mène {jours} j" if jours else "")))

    # --- liens vivants du Miroir ----------------------------------------
    if miroir:
        if miroir.get("bloque"):
            g.liens.append(Lien(de="AG-10", vers="AG-00", type="bloque",
                                poids=1.0, etiquette="BLOCAGE"))
        else:
            s = float(miroir.get("score", 0.0))
            if abs(s) >= SEUIL_LIEN:
                g.liens.append(Lien(
                    de="AG-10", vers="AG-00",
                    type="confirme" if s > 0 else "contredit",
                    poids=round(abs(s), 3), etiquette=f"score {s:+.2f}"))

    # --- le debat contradictoire -----------------------------------------
    if avocat and avocat.get("objections"):
        g.liens.append(Lien(
            de="AG-16", vers=avocat.get("cible", "AG-00"),
            type="bloque" if avocat.get("bloque") else "contredit",
            poids=1.0 if avocat.get("bloque") else 0.6,
            etiquette=f"{len(avocat['objections'])} objection(s)"))

    if defense and defense.get("arguments"):
        g.liens.append(Lien(
            de="AG-18", vers=defense.get("cible", "AG-00"), type="confirme",
            poids=0.6, etiquette=f"{len(defense['arguments'])} argument(s)"))

    return g


# --------------------------------------------------------------------------
def depuis_verdict(v, cible: str = "AG-03") -> tuple[dict, dict, dict]:
    """Traduit un Verdict d'avocats.py en (avocat, defense, positions).

    `positions` se fusionne dans les cartes avant `construire()` :

        for c in cartes:
            if c["code"] in positions:
                c["position"] = positions[c["code"]]

    Le silence d'un avocat produit un dict vide, donc AUCUN lien : sur le
    graphe il reste un noeud gris. C'est voulu — un avocat muet doit se
    voir, sinon on ne remarque jamais qu'un agent a cesse de fonctionner.
    """
    avocat = {"cible": cible,
              "objections": [a.texte for a in v.contre],
              "bloque": v.verdict == "BLOQUÉ"} if v.contre else {}
    defense = {"cible": cible,
               "arguments": [a.texte for a in v.pour]} if v.pour else {}
    positions = {"AG-16": "contre" if v.contre else "neutre",
                 "AG-18": "pour" if v.pour else "neutre"}
    return avocat, defense, positions


# --------------------------------------------------------------------------
def _demo() -> None:
    cartes = [
        {"code": "AG-01", "statut": "STREAMING", "conviction": 90,
         "activites": ["géopolitique calme — 16 titres"]},
        {"code": "AG-02", "statut": "STREAMING", "conviction": 26,
         "activites": ["H4 : 50% haussier · RSI 42"]},
        {"code": "AG-03", "statut": "SCANNING", "conviction": 60,
         "activites": ["filtre de tendance non satisfait"]},
        {"code": "AG-04", "statut": "STREAMING", "conviction": 25,
         "activites": ["M15 : ABC — C en cours"]},
        {"code": "AG-05", "statut": "STREAMING", "conviction": 60,
         "activites": ["AEM +13.4% vs or +0.9%"]},
        {"code": "AG-09", "statut": "STREAMING", "conviction": 100,
         "activites": ["6 corrélations en transition"]},
        {"code": "AG-10", "statut": "BLOCAGE", "conviction": 0,
         "activites": ["0 confirment · 13 contredisent"]},
        {"code": "AG-11", "statut": "STREAMING", "conviction": 20,
         "activites": ["baissier, dispersé · 10 actifs"]},
        {"code": "AG-12", "statut": "STREAMING", "conviction": 100,
         "activites": ["haussier large, en bloc"]},
        {"code": "AG-13", "statut": "STREAMING", "conviction": 20,
         "activites": ["haussier, groupé"]},
        {"code": "AG-14", "statut": "STREAMING", "conviction": 100,
         "activites": ["haussier large, groupé"]},
        {"code": "AG-15", "statut": "STREAMING", "conviction": 30,
         "activites": ["crypto mène actions de 2 j"]},
        {"code": "AG-16", "statut": "VEILLE", "conviction": 25,
         "activites": ["aucun setup à contester"]},
        {"code": "AG-18", "statut": "STREAMING", "conviction": 40,
         "activites": ["stop à 1,67 ATR · 3 TF alignés"]},
        # AG-00 absent volontairement : il doit ressortir MUET
    ]
    # Les positions prises sur le signal en cours.
    positions = {"AG-02": "pour", "AG-04": "pour", "AG-05": "pour",
                 "AG-10": "contre", "AG-11": "contre", "AG-13": "pour",
                 "AG-16": "contre", "AG-18": "pour"}
    for c in cartes:
        if c["code"] in positions:
            c["position"] = positions[c["code"]]
    inter = {"liens": [
        {"de": "crypto", "vers": "actions", "corr": 0.47, "meneur": "crypto", "jours": 2},
        {"de": "forex", "vers": "matieres", "corr": 0.29, "meneur": "—", "jours": 0},
    ]}
    miroir = {"score": -1.0, "bloque": True, "base": 2.28}
    avocat = {"cible": "AG-03", "objections": ["news FOMC dans 3 h"],
              "bloque": False}
    defense = {"cible": "AG-03",
               "arguments": ["stop à 1,67 ATR", "3 timeframes alignés"]}

    g = construire(cartes, inter, miroir, avocat, defense)
    print(g.resume(), "\n")
    signe = {"pour": "+", "contre": "−", "neutre": "·"}
    for c in COUCHES:
        ns = [n for n in g.noeuds if n.couche == c]
        if ns:
            print(f"  {c:<12} " + " · ".join(
                f"{signe[n.position]}{n.emoji}{n.nom}"
                f"({n.conviction}%{'' if n.vivant else ' MUET'})"
                for n in ns))
    print("\n  liens porteurs d'information :")
    for l in g.liens:
        if l.type != "alimente":
            fl = f" ══{l.jours}j═>" if l.jours else " ——>"
            print(f"    {l.de}{fl} {l.vers}   {l.type:<11} {l.etiquette}")


if __name__ == "__main__":
    _demo()
