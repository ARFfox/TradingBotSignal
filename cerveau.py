#!/usr/bin/env python3
"""
LE CERVEAU — la boucle vivante du superviseur.

    python3 cerveau.py           # démonstration
    python3 cerveau.py journal.json cerveau.json

Le manque que ce module comble
-------------------------------
Cinq calibrations existent déjà et fonctionnent :

    superviseur_apprenant.poids_agents()      poids des agents
    avocats.calibrer()                        poids des arguments
    figures.calibrer()                        poids des figures
    direction.calibrer()                      poids des sources de direction
    parametres_agents.evaluer_parametre()     réglages, walk-forward

**Personne ne les lance ensemble, et leurs résultats ne reviennent nulle
part.** Le site affiche des poids figés pendant que le journal grossit. Ce
module est la boucle : il lance tout, écrit l'état sur disque, et le site
lit ce fichier. C'est ça, « le superviseur est vivant sur tout le site ».

Les quatre règles qui séparent apprendre d'osciller
----------------------------------------------------
1. **On n'apprend que de données NOUVELLES.** Re-calibrer sur les mêmes
   405 signaux ne produit pas un nouveau savoir : c'est la même conclusion
   re-dérivée, et à force de re-chercher dans le même journal on finit par
   y trouver ce qu'on veut. Sous `N_MIN_NOUVEAUX` résolus depuis le dernier
   cycle, le cerveau ne bouge pas et **dit pourquoi**.

2. **Un poids ne peut pas sauter.** `DELTA_MAX` par cycle. Un cerveau dont
   les poids changent de 0,1 à 2,0 en un cycle n'apprend pas, il réagit au
   dernier trade.

3. **Tout changement est journalisé, avec son avant/après et son motif.**
   Rien n'est irréversible : `revenir_a(version)` rejoue l'état précédent.

4. **Il affiche ce qu'il a appris, pas qu'il tourne.** Une pastille verte
   « superviseur actif » sur un cerveau qui n'a rien appris depuis trois
   semaines est un mensonge décoratif. `etat_live()` affiche la DATE du
   dernier apprentissage réel et le nombre de signaux qui l'ont nourri.

Ce que le cerveau sait de lui-même
-----------------------------------
`sante()` liste ce qui l'empêche d'apprendre, en clair. Sur ton journal
actuel il dirait par exemple : « 314 SL sur 317 sont indéterminés — je ne
peux rien apprendre des stops tant que l'ATR n'est pas journalisé. » Un
cerveau qui ne sait pas dire ce qui lui manque ne peut pas être réparé.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
N_MIN_NOUVEAUX = 20      # résolus nouveaux exigés avant de rebouger les poids
DELTA_MAX = 0.35         # variation maximale d'un poids en un cycle
N_MAX_CHANGEMENTS = 400  # taille du journal des changements conservé
FICHIER = Path("cerveau.json")


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Changement:
    quand: str
    quoi: str          # "argument:stop_dans_le_bruit"
    avant: float
    apres: float
    motif: str
    n_base: int        # combien de résolus fondent ce changement
    version: int = 0   # version du cerveau APRÈS ce changement

    def __str__(self) -> str:
        fl = "▲" if self.apres > self.avant else "▼"
        return (f"{fl} {self.quoi} : {self.avant:.2f} → {self.apres:.2f} "
                f"({self.motif}, n={self.n_base})")


@dataclass
class Etat:
    version: int = 0
    maj: str = ""
    n_resolus: int = 0
    n_au_dernier_apprentissage: int = 0
    dernier_apprentissage: str = ""
    poids: dict = field(default_factory=dict)   # famille -> {code: poids}
    combos_coupes: list = field(default_factory=list)
    seuil_emission: float | None = None
    changements: list = field(default_factory=list)
    motif_dernier_cycle: str = ""
    n_neuf_dernier_cycle: int = 0      # combien de résolus ont nourri le dernier cycle
    n_changements_dernier_cycle: int = 0

    @property
    def n_depuis_apprentissage(self) -> int:
        return self.n_resolus - self.n_au_dernier_apprentissage

    def tous_les_poids(self) -> dict:
        """Aplati : `{"argument:stop_dans_le_bruit": 1.4, ...}`."""
        return {f"{fam}:{code}": p
                for fam, d in self.poids.items() for code, p in d.items()}

    def n_mesures(self) -> int:
        return sum(1 for p in self.tous_les_poids().values() if p > 0)


# ==========================================================================
# 1. LE CYCLE
# ==========================================================================
def _lisser(avant: float, propose: float) -> float:
    """Un poids se déplace d'au plus DELTA_MAX par cycle.

    Sans ce frein, un cerveau nourri de 20 nouveaux trades peut faire passer
    un poids de 0,1 à 2,0 — ce n'est pas de l'apprentissage, c'est une
    réaction au dernier trade. Le lissage rend l'adaptation lente ET
    l'empêche de partir en oscillation.
    """
    ecart = propose - avant
    if abs(ecart) <= DELTA_MAX:
        return round(propose, 3)
    return round(avant + (DELTA_MAX if ecart > 0 else -DELTA_MAX), 3)


def cycle(journal, etat: Etat | None = None,
          calibrations: dict | None = None, forcer: bool = False) -> Etat:
    """Un tour de cerveau.

    `journal` : la liste des signaux.
    `calibrations` : `{famille: {code: poids}}` déjà calculé par les modules
        (`avocats.calibrer()`, `figures.calibrer()`, …). Injecté plutôt
        qu'importé pour que ce module reste testable seul et ne force pas
        l'ordre de chargement.
    `forcer` : passe outre le seuil de données nouvelles. À n'utiliser que
        pour un rattrapage manuel — la règle existe pour une raison.
    """
    e = etat or Etat()
    resolus = [s for s in journal
               if (s.get("statut") if isinstance(s, dict)
                   else getattr(s, "statut", None)) in ("TP", "SL")]
    n = len(resolus)
    nouveau = Etat(
        version=e.version, maj=_maintenant(), n_resolus=n,
        n_au_dernier_apprentissage=e.n_au_dernier_apprentissage,
        dernier_apprentissage=e.dernier_apprentissage,
        poids={k: dict(v) for k, v in e.poids.items()},
        combos_coupes=list(e.combos_coupes), seuil_emission=e.seuil_emission,
        changements=list(e.changements))

    n_neuf = n - e.n_au_dernier_apprentissage
    if not forcer and n_neuf < N_MIN_NOUVEAUX:
        nouveau.motif_dernier_cycle = (
            f"{n_neuf} résolu(s) nouveau(x) depuis le dernier apprentissage — "
            f"il en faut {N_MIN_NOUVEAUX}. Rien n'a bougé, et c'est voulu : "
            f"recalibrer sur les mêmes données ne crée aucun savoir.")
        return nouveau

    if not calibrations:
        nouveau.motif_dernier_cycle = "aucune calibration fournie — rien à apprendre"
        return nouveau

    changements: list[Changement] = []
    for famille, poids_proposes in calibrations.items():
        actuels = nouveau.poids.setdefault(famille, {})
        for code, propose in (poids_proposes or {}).items():
            propose = float(propose)
            avant = float(actuels.get(code, 0.0))
            apres = _lisser(avant, propose)
            # On enregistre TOUJOURS le code, même à zéro. Omettre les poids
            # nuls faisait afficher « 3/3 poids mesurés » alors que trois
            # autres sources avaient été mesurées ET jugées inutiles : le
            # dénominateur ne comptait que ce qui avait bougé.
            deja = code in actuels
            if not deja:
                # PREMIÈRE mesure d'un poids : on l'applique en entier.
                # Le lissage existe pour empêcher d'osciller ENTRE deux
                # mesures, pas pour freiner la première — il n'y a aucune
                # croyance antérieure à protéger, et la brider imposait six
                # cycles pour atteindre un poids de 2,0.
                apres = round(propose, 3)
            actuels[code] = apres
            if deja and abs(apres - avant) < 0.01:
                continue
            if not deja and apres == 0.0:
                continue
            motif = ("première mesure" if not deja else
                     "gagne du poids" if apres > avant else
                     "en perd" if apres > 0 else "réduit au silence")
            if deja and abs(propose - apres) > 0.01:
                motif += f" (proposé {propose:.2f}, lissé à ±{DELTA_MAX})"
            changements.append(Changement(nouveau.maj, f"{famille}:{code}",
                                          round(avant, 3), apres, motif, n,
                                          e.version + 1))

    nouveau.changements = (nouveau.changements + [asdict(c) for c in changements]
                           )[-N_MAX_CHANGEMENTS:]
    nouveau.version = e.version + 1
    nouveau.n_au_dernier_apprentissage = n
    nouveau.dernier_apprentissage = nouveau.maj
    nouveau.n_neuf_dernier_cycle = n_neuf
    nouveau.n_changements_dernier_cycle = len(changements)
    nouveau.motif_dernier_cycle = (
        f"{len(changements)} poids modifié(s) sur {n_neuf} nouveaux résolus"
        if changements else
        f"{n_neuf} nouveaux résolus analysés — aucun poids n'a bougé, "
        f"les mesures confirment l'état actuel")
    return nouveau


def revenir_a(etat: Etat, version: int) -> Etat:
    """Rejoue l'état à une version antérieure, en défaisant les changements.

    « Tout changement automatique est réversible » n'est une règle que si
    quelqu'un a écrit le retour en arrière.
    """
    if version >= etat.version:
        return etat
    e = Etat(version=version, maj=_maintenant(), n_resolus=etat.n_resolus,
             n_au_dernier_apprentissage=etat.n_au_dernier_apprentissage,
             dernier_apprentissage=etat.dernier_apprentissage,
             poids={k: dict(v) for k, v in etat.poids.items()},
             combos_coupes=list(etat.combos_coupes),
             seuil_emission=etat.seuil_emission,
             changements=list(etat.changements))

    # On défait à REBOURS tout ce qui porte une version > celle visée.
    # Chaque changement connaît sa version : sans ça il fallait deviner
    # combien en défaire, et le premier essai en défaisait beaucoup trop.
    a_defaire = [c for c in etat.changements if c.get("version", 0) > version]
    for c in reversed(a_defaire):
        fam, _, code = c["quoi"].partition(":")
        if fam in e.poids and code in e.poids[fam]:
            e.poids[fam][code] = c["avant"]
    e.changements = [c for c in etat.changements if c.get("version", 0) <= version]
    e.motif_dernier_cycle = (f"retour manuel à la version {version} — "
                             f"{len(a_defaire)} changement(s) défait(s)")
    return e


# ==========================================================================
# 2. CE QUE LE CERVEAU SAIT DE LUI-MÊME
# ==========================================================================
def sante(etat: Etat, journal, audits: dict | None = None) -> list[dict]:
    """Ce qui empêche le cerveau d'apprendre, nommé en clair.

    Un cerveau qui ne sait pas dire ce qui lui manque ne peut pas être
    réparé — on le regarde tourner en croyant qu'il progresse.
    """
    out = []
    a = audits or {}

    indet = int(a.get("sl_indetermines", 0))
    total_sl = int(a.get("sl_total", 0))
    if total_sl and indet / total_sl > 0.5:
        out.append({"gravite": "bloquant", "quoi": "audit des stops",
                    "detail": f"{indet} SL sur {total_sl} sont indéterminés",
                    "pourquoi": "l'ATR à l'émission manque au journal",
                    "effet": "impossible de distinguer un stop trop serré "
                             "d'une erreur de direction — deux pannes "
                             "opposées, deux corrections opposées",
                    "action": "APPLIQUER.md étape 1"})

    tous = etat.tous_les_poids()
    if tous and etat.n_mesures() == 0:
        out.append({"gravite": "bloquant", "quoi": "aucun poids mesuré",
                    "detail": f"0 sur {len(tous)} sources portent un poids",
                    "pourquoi": "pas assez de résolus par source",
                    "effet": "le système décrit le marché, il ne le prévoit pas",
                    "action": "laisser le journal grossir"})

    if etat.n_depuis_apprentissage < N_MIN_NOUVEAUX and etat.version > 0:
        out.append({"gravite": "normal", "quoi": "en attente de données",
                    "detail": f"{etat.n_depuis_apprentissage} nouveau(x) "
                              f"résolu(s) sur {N_MIN_NOUVEAUX} requis",
                    "pourquoi": "on n'apprend que de données nouvelles",
                    "effet": "les poids restent stables — c'est normal",
                    "action": "aucune"})

    if etat.seuil_emission is None and etat.n_resolus >= 50:
        out.append({"gravite": "attention", "quoi": "seuil d'émission",
                    "detail": "aucun seuil mesuré",
                    "pourquoi": "seuil_optimal() n'a pas été lancé, ou aucun "
                                "seuil ne rend le système positif",
                    "effet": "le filtrage d'émission est deviné, pas mesuré",
                    "action": "APPLIQUER.md étape 4"})

    if a.get("calibration_inversee"):
        out.append({"gravite": "bloquant", "quoi": "note inversée",
                    "detail": a["calibration_inversee"],
                    "pourquoi": "plus le système est confiant, moins il a raison",
                    "effet": "filtrer sur la note sélectionne les perdants",
                    "action": "ne PAS filtrer sur la note (APPLIQUER.md §2.2)"})
    return out


# ==========================================================================
# 3. LA PRÉSENCE SUR LE SITE
# ==========================================================================
def etat_live(etat: Etat, problemes: list | None = None) -> dict:
    """Le bandeau que chaque page affiche. Compact, honnête, daté.

    ⚠️ `statut` ne vaut JAMAIS « actif » parce que le processus tourne. Il
    décrit ce que le cerveau a APPRIS. Une pastille verte sur un cerveau qui
    n'a rien appris depuis trois semaines apprend au lecteur à ne plus la
    regarder — c'est pire que pas de pastille du tout.
    """
    p = problemes or []
    bloquants = [x for x in p if x.get("gravite") == "bloquant"]

    # ⚠️ L'ordre compte. « vient d'apprendre » passe AVANT « en attente » :
    # juste après un cycle, n_depuis vaut 0 par construction, et afficher
    # « en attente 0/20 » à l'instant où le cerveau vient de modifier ses
    # poids donne exactement l'inverse de l'information utile.
    vient_d_apprendre = etat.n_changements_dernier_cycle > 0
    if bloquants:
        statut, couleur = "bridé", "rouge"
        phrase = bloquants[0]["detail"]
    elif etat.version == 0:
        statut, couleur = "jamais entraîné", "gris"
        phrase = "aucun cycle n'a encore tourné"
    elif vient_d_apprendre and etat.n_depuis_apprentissage == 0:
        statut, couleur = "vient d'apprendre", "vert"
        phrase = (f"{etat.n_changements_dernier_cycle} poids modifié(s) sur "
                  f"{etat.n_neuf_dernier_cycle} nouveaux résolus")
    elif etat.n_depuis_apprentissage < N_MIN_NOUVEAUX:
        statut, couleur = "en attente", "ambre"
        phrase = (f"{etat.n_depuis_apprentissage}/{N_MIN_NOUVEAUX} nouveaux "
                  f"résolus avant le prochain apprentissage")
    else:
        statut, couleur = "apprend", "vert"
        phrase = etat.motif_dernier_cycle

    derniers = [Changement(**c) for c in etat.changements[-3:]]
    tous = etat.tous_les_poids()
    return {
        "statut": statut, "couleur": couleur, "phrase": phrase,
        "version": etat.version,
        "dernier_apprentissage": etat.dernier_apprentissage or "—",
        "n_resolus": etat.n_resolus,
        "n_depuis": etat.n_depuis_apprentissage,
        "n_mesures": etat.n_mesures(), "n_total_poids": len(tous),
        "derniers_changements": [str(c) for c in derniers],
        "problemes": p,
    }


def bandeau_texte(live: dict) -> str:
    """Une ligne pour l'en-tête du site."""
    icone = {"vert": "●", "ambre": "◐", "rouge": "■",
             "gris": "○"}.get(live["couleur"], "·")
    return (f"{icone} Superviseur — {live['statut']} · "
            f"v{live['version']} · {live['n_mesures']}/{live['n_total_poids']} "
            f"poids mesurés · {live['phrase']}")


# ==========================================================================
# 4. PERSISTANCE
# ==========================================================================
def charger(chemin: Path = FICHIER) -> Etat:
    if not Path(chemin).exists():
        return Etat()
    try:
        d = json.loads(Path(chemin).read_text(encoding="utf-8"))
        return Etat(**{k: v for k, v in d.items()
                       if k in Etat.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError, ValueError):
        # Un fichier d'état corrompu ne doit pas empêcher le site de démarrer.
        return Etat()


def sauver(etat: Etat, chemin: Path = FICHIER) -> None:
    Path(chemin).write_text(
        json.dumps(asdict(etat), ensure_ascii=False, indent=2), encoding="utf-8")


def rapport(etat: Etat, problemes: list | None = None) -> str:
    live = etat_live(etat, problemes)
    l = [f"# Cerveau — {live['statut']}", "",
         f"**{bandeau_texte(live)}**", "",
         f"- version **{etat.version}** · dernier apprentissage "
         f"{etat.dernier_apprentissage or 'jamais'}",
         f"- {etat.n_resolus} résolus au journal, "
         f"{etat.n_depuis_apprentissage} depuis le dernier cycle",
         f"- {etat.n_mesures()} poids mesurés sur {len(etat.tous_les_poids())}",
         "", f"> {etat.motif_dernier_cycle}"]

    if problemes:
        l += ["", "## Ce qui l'empêche d'apprendre", ""]
        for p in problemes:
            marque = {"bloquant": "🔴", "attention": "🟠",
                      "normal": "⚪"}.get(p["gravite"], "•")
            l.append(f"{marque} **{p['quoi']}** — {p['detail']}  ")
            l.append(f"   *{p['pourquoi']}* → {p['effet']}  ")
            l.append(f"   → `{p['action']}`")
            l.append("")

    if etat.changements:
        l += ["## Ce qu'il a appris en dernier", "",
              "| quand | quoi | avant | après | motif |", "|---|---|---:|---:|---|"]
        for c in etat.changements[-12:][::-1]:
            l.append(f"| {c['quand'][:16]} | `{c['quoi']}` | {c['avant']:.2f} "
                     f"| **{c['apres']:.2f}** | {c['motif']} |")
        l += ["", f"*{len(etat.changements)} changement(s) au journal. "
                  f"`revenir_a(etat, v)` défait tout retour en arrière.*"]
    else:
        l += ["", "Aucun changement enregistré — le cerveau n'a encore rien "
                  "modifié. Ce n'est pas une panne tant que le journal n'a pas "
                  "assez de résolus."]
    return "\n".join(l) + "\n"


# --------------------------------------------------------------------------
def _demo() -> None:
    import random
    rng = random.Random(9)

    def journal(n):
        return [{"statut": "TP" if rng.random() < .25 else "SL",
                 "r_realise": 2.1 if rng.random() < .25 else -1.0}
                for _ in range(n)]

    print("=" * 74, "\n  1. PREMIER CYCLE — le cerveau apprend pour la 1re fois\n", "=" * 74)
    e = cycle(journal(120), Etat(), {
        "argument": {"stop_dans_le_bruit": 1.8, "rr_insuffisant": 0.9,
                     "contre_le_regime": 0.0},
        "figure": {"marteau": 0.0, "double_sommet": 0.0},
        "source": {"structure_ema": 1.2}})
    print(bandeau_texte(etat_live(e)))
    for c in e.changements[-5:]:
        print("   ", Changement(**c))

    print("\n" + "=" * 74, "\n  2. MÊMES DONNÉES — il refuse de rebouger\n", "=" * 74)
    e2 = cycle(journal(120)[:120], e, {"argument": {"stop_dans_le_bruit": 0.1}})
    print(bandeau_texte(etat_live(e2)))
    print("    version inchangée :", e2.version == e.version)

    print("\n" + "=" * 74, "\n  3. DONNÉES NEUVES — mais le saut est lissé\n", "=" * 74)
    e3 = cycle(journal(160), e, {"argument": {"stop_dans_le_bruit": 0.1}})
    print(bandeau_texte(etat_live(e3)))
    for c in e3.changements[-2:]:
        print("   ", Changement(**c))
    print(f"    proposé 0.10 après 1.80, appliqué "
          f"{e3.poids['argument']['stop_dans_le_bruit']:.2f} "
          f"— un poids se déplace d'au plus {DELTA_MAX} par cycle")

    print("\n" + "=" * 74, "\n  4. SANTÉ — ce qu'il ne peut pas apprendre\n", "=" * 74)
    p = sante(e3, journal(160), {
        "sl_indetermines": 314, "sl_total": 317,
        "calibration_inversee": "bande 40–60 % : 17 % réel contre 25 % en 20–40 %"})
    print(rapport(e3, p))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        j = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        f = Path(sys.argv[2]) if len(sys.argv) > 2 else FICHIER
        nouveau = cycle(j, charger(f))
        sauver(nouveau, f)
        print(rapport(nouveau, sante(nouveau, j)))
    else:
        _demo()
