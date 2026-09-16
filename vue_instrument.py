#!/usr/bin/env python3
"""
VUE PAR INSTRUMENT — tout ce que la page doit afficher quand on clique sur
un instrument : son historique, son taux, ses 5 timeframes, ses badges.

    python3 vue_instrument.py        # démonstration

Pourquoi ce module existe
-------------------------
Aujourd'hui la page mélange tout : un taux global de 21,7 % qui vaut pour
l'or, pour le Bitcoin et pour EUR/USD à la fois — donc pour aucun des trois.
Cliquer sur l'or doit montrer l'or : son historique, son taux, ses
timeframes, rien d'autre.

C'est aussi ce dont le superviseur a besoin. Il coupe déjà par couple
(instrument × timeframe) ; la page doit montrer la même découpe, sinon on
regarde un chiffre et le système en applique un autre.

LE PIÈGE, et il est énorme ici
-------------------------------
405 résolus répartis sur ~25 instruments × 5 timeframes = **3,2 signaux par
case**. Un « taux de réussite » sur 3 signaux n'est pas une mesure, c'est un
tirage à pile ou face affiché en gras.

Le module refuse donc de calculer un taux sous `N_MIN_TAUX` résolus et
renvoie `None`. La page doit alors écrire **« échantillon insuffisant
(3/20) »** À LA PLACE du pourcentage — jamais à côté, jamais en petit.

Un « 67 % » sur 3 trades fait prendre des décisions. Un « insuffisant »
n'en fait prendre aucune. C'est exactement ce qu'on veut dans les deux cas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pips import bilan as bilan_pips, taille_pip
from statistiques import taux_hasard, wilson

# --------------------------------------------------------------------------
N_MIN_TAUX = 20        # sous ce seuil, aucun taux n'est affiché
N_MIN_VERDICT = 20     # sous ce seuil, aucun couple n'est coupé ni autorisé
SEUIL_COUPE = -0.10    # R moyen sous lequel un couple est coupé
SEUIL_AUTORISE = 0.05  # R moyen au-dessus duquel un couple est autorisé
TIMEFRAMES = ("H4", "H1", "M30", "M15", "M5")


def _c(s, nom, defaut=None):
    """Lit un champ, que `s` soit un dict du journal ou une dataclasse."""
    if isinstance(s, dict):
        return s.get(nom, defaut)
    return getattr(s, nom, defaut)


def _resolu(s) -> bool:
    return _c(s, "statut") in ("TP", "SL")


def _r(s) -> float | None:
    """R réalisé, avec repli sur la géométrie si `r_realise` est absent.

    ⚠️ Le repli existe parce que `r_realise` n'est pas encore alimenté dans
    le journal (c'est l'étape 1). Il le sera : ce chemin doit disparaître.
    Tant qu'il sert, le profit factor de la page est faux — c'est la cause
    du « 0.00 » affiché alors que la vraie valeur est 0,62.
    """
    r = _c(s, "r_realise")
    if r is not None:
        return float(r)
    e, sl, tp = _c(s, "entree"), _c(s, "sl"), _c(s, "tp")
    st = _c(s, "statut")
    if None in (e, sl, tp) or st not in ("TP", "SL"):
        return None
    risque = abs(e - sl)
    if not risque:
        return None
    return abs(tp - e) / risque if st == "TP" else -1.0


# ==========================================================================
@dataclass
class Case:
    """Une case du tableau : un instrument, ou un couple instrument × TF."""
    cle: str
    n_resolus: int = 0
    n_tp: int = 0
    n_attente: int = 0
    n_expire: int = 0
    r_total: float = 0.0
    pips_net: float = 0.0
    rr_moyen: float = 0.0

    @property
    def mesurable(self) -> bool:
        return self.n_resolus >= N_MIN_TAUX

    @property
    def taux(self) -> float | None:
        """None = pas assez de données. La page écrit « insuffisant »."""
        return self.n_tp / self.n_resolus if self.mesurable else None

    @property
    def ic(self) -> tuple[float, float] | None:
        return wilson(self.n_tp, self.n_resolus) if self.mesurable else None

    @property
    def r_moyen(self) -> float | None:
        return self.r_total / self.n_resolus if self.mesurable else None

    @property
    def hasard(self) -> float:
        """Le taux qu'une pièce lancée obtiendrait à ce R:R. La seule
        référence honnête — jamais 50 %."""
        return taux_hasard(self.rr_moyen)

    @property
    def verdict(self) -> str:
        if self.n_resolus < N_MIN_VERDICT:
            return "INSUFFISANT"
        m = self.r_moyen or 0.0
        if m <= SEUIL_COUPE:
            return "COUPÉ"
        if m >= SEUIL_AUTORISE:
            return "AUTORISÉ"
        return "OBSERVATION"

    @property
    def texte_taux(self) -> str:
        """Ce que la page affiche, littéralement. Le module décide du texte
        pour que deux pages ne puissent pas l'écrire différemment."""
        if not self.mesurable:
            return f"échantillon insuffisant ({self.n_resolus}/{N_MIN_TAUX})"
        b, h = self.ic
        return (f"{self.taux:.0%} ({self.n_tp}/{self.n_resolus}) "
                f"· IC [{b:.0%}–{h:.0%}] · hasard {self.hasard:.0%}")


@dataclass
class Fiche:
    """Tout ce que la page affiche pour UN instrument."""
    instrument: str
    marche: str = "?"
    unite: str = "pips"
    global_: Case = field(default_factory=lambda: Case("global"))
    timeframes: dict[str, Case] = field(default_factory=dict)
    tf_avec_signal: list[str] = field(default_factory=list)
    signaux: list = field(default_factory=list)      # historique filtré

    @property
    def badge(self) -> int:
        """Le chiffre rouge sur la pastille : signaux EN COURS, pas
        l'historique. Un badge qui compte des trades finis ne se vide
        jamais et on arrête de le regarder."""
        return len(self.tf_avec_signal)

    @property
    def sous_le_hasard(self) -> bool:
        t = self.global_.taux
        return t is not None and t < self.global_.hasard


# ==========================================================================
def _remplir(case: Case, signaux) -> None:
    rr = []
    for s in signaux:
        st = _c(s, "statut")
        if st == "en_attente":
            case.n_attente += 1
            continue
        if st == "expire":
            # Entrée jamais touchée : ne compte dans AUCUN taux.
            case.n_expire += 1
            continue
        if st not in ("TP", "SL"):
            continue
        case.n_resolus += 1
        if st == "TP":
            case.n_tp += 1
        r = _r(s)
        if r is not None:
            case.r_total += r
        e, sl, tp = _c(s, "entree"), _c(s, "sl"), _c(s, "tp")
        if None not in (e, sl, tp) and abs(e - sl):
            rr.append(abs(tp - e) / abs(e - sl))
    case.rr_moyen = sum(rr) / len(rr) if rr else 0.0
    case.pips_net = bilan_pips(signaux).net


def fiche(signaux, instrument: str, signaux_actifs=None) -> Fiche:
    """La fiche complète d'un instrument.

    `signaux` : le journal entier — le filtrage se fait ici, pour qu'aucune
    page ne puisse oublier de filtrer.
    `signaux_actifs` : les signaux EN COURS (non résolus, affichés), qui
    servent aux badges. Séparés volontairement de l'historique.
    """
    mien = [s for s in signaux if _c(s, "instrument") == instrument]
    f = Fiche(instrument)
    if mien:
        f.marche = _c(mien[0], "marche", "?") or "?"
    f.unite = taille_pip(instrument)[1]
    f.signaux = sorted(mien, key=lambda s: _c(s, "cree_ts", 0) or 0, reverse=True)

    _remplir(f.global_, mien)
    for tf in TIMEFRAMES:
        c = Case(tf)
        _remplir(c, [s for s in mien if _c(s, "tf") == tf])
        f.timeframes[tf] = c

    for s in (signaux_actifs or []):
        if _c(s, "instrument") == instrument:
            tf = _c(s, "tf")
            if tf and tf not in f.tf_avec_signal:
                f.tf_avec_signal.append(tf)
    f.tf_avec_signal.sort(key=lambda t: TIMEFRAMES.index(t)
                          if t in TIMEFRAMES else 99)
    return f


def toutes_les_fiches(signaux, signaux_actifs=None) -> list[Fiche]:
    noms = {_c(s, "instrument") for s in signaux if _c(s, "instrument")}
    noms |= {_c(s, "instrument") for s in (signaux_actifs or [])
             if _c(s, "instrument")}
    fiches = [fiche(signaux, n, signaux_actifs) for n in sorted(noms)]
    return sorted(fiches, key=lambda f: (-f.badge, -f.global_.n_resolus))


def badges_par_marche(fiches: list[Fiche]) -> dict[str, int]:
    """Le chiffre de la pastille sur chaque bouton de marché : la somme de
    ses instruments. Il descend quand on traite les signaux."""
    out: dict[str, int] = {}
    for f in fiches:
        if f.badge:
            out[f.marche] = out.get(f.marche, 0) + f.badge
    return out


# ==========================================================================
def rapport(f: Fiche) -> str:
    """Le texte que la page reprend, pour qu'elle ne réinvente aucun calcul."""
    g = f.global_
    l = [f"# {f.instrument} — {f.marche}", "",
         f"**{g.texte_taux}**", "",
         f"R cumulé **{g.r_total:+.1f}R** · "
         f"{'+' if g.pips_net >= 0 else '−'}{abs(g.pips_net):,.0f} {f.unite}"
         .replace(",", " ")
         + f" · {g.n_attente} en attente · {g.n_expire} jamais entrés", ""]

    if f.sous_le_hasard:
        l += [f"> ⚠️ **{g.taux:.0%} contre {g.hasard:.0%} pour une pièce "
              f"lancée à ce R:R.** Cet instrument prédit moins bien que le "
              f"hasard : le problème n'est pas le tri des signaux, c'est "
              f"leur construction.", ""]

    l += ["| TF | n | taux | R moyen | pips | verdict | signal |",
          "|---|---:|---|---:|---:|---|---|"]
    for tf in TIMEFRAMES:
        c = f.timeframes[tf]
        taux = f"{c.taux:.0%}" if c.taux is not None else f"— ({c.n_resolus}/{N_MIN_TAUX})"
        rm = f"{c.r_moyen:+.2f}R" if c.r_moyen is not None else "—"
        sig = "🔴 en cours" if tf in f.tf_avec_signal else ""
        l.append(f"| **{tf}** | {c.n_resolus} | {taux} | {rm} "
                 f"| {c.pips_net:+,.0f} | {c.verdict} | {sig} |".replace(",", " "))

    insuffisants = [tf for tf in TIMEFRAMES
                    if f.timeframes[tf].n_resolus < N_MIN_TAUX]
    if insuffisants:
        l += ["", f"> {len(insuffisants)}/5 timeframes n'ont pas assez de "
                  f"données pour un taux : **{', '.join(insuffisants)}**. "
                  f"C'est normal — 405 résolus répartis sur 25 instruments × "
                  f"5 timeframes font ~3 signaux par case. Ne lis pas un "
                  f"pourcentage là où le module écrit « insuffisant »."]
    return "\n".join(l) + "\n"


# --------------------------------------------------------------------------
def _demo() -> None:
    import random
    rng = random.Random(4)
    jour = []
    plan = [("XAU/USD", "matieres", 240), ("EUR/USD", "forex", 60),
            ("BTC/USD", "crypto", 40), ("ETH/USD", "crypto", 12)]
    i = 0
    for inst, marche, n in plan:
        px = {"XAU/USD": 4348.0, "EUR/USD": 1.085,
              "BTC/USD": 75713.0, "ETH/USD": 2396.0}[inst]
        for _ in range(n):
            i += 1
            tf = rng.choice(TIMEFRAMES)
            risque = px * 0.004
            gagne = rng.random() < (0.30 if inst == "BTC/USD" else 0.21)
            jour.append({"id": f"s{i}", "instrument": inst, "marche": marche,
                         "tf": tf, "sens": "achat", "entree": px,
                         "sl": px - risque, "tp": px + 2.1 * risque,
                         "cree_ts": 1_750_000_000 + i * 900,
                         "statut": "TP" if gagne else "SL"})
    actifs = [{"instrument": "BTC/USD", "tf": "H4", "marche": "crypto"},
              {"instrument": "XAU/USD", "tf": "M15", "marche": "matieres"},
              {"instrument": "XAU/USD", "tf": "M5", "marche": "matieres"}]

    for f in toutes_les_fiches(jour, actifs):
        print(rapport(f))
        print(f"badge : {f.badge}  ·  timeframes en signal : "
              f"{f.tf_avec_signal or '—'}\n" + "=" * 74 + "\n")
    print("badges par marché :", badges_par_marche(toutes_les_fiches(jour, actifs)))


if __name__ == "__main__":
    _demo()
