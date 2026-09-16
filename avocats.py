#!/usr/bin/env python3
"""
AG-16 AVOCAT DU DIABLE · AG-18 AVOCAT DE LA DÉFENSE — le débat contradictoire.

    python3 avocats.py        # démonstration sur des cas réels du journal

Pourquoi deux avocats et pas un
-------------------------------
Un système qui n'a qu'un contradicteur (AG-16) apprend à se méfier de tout.
Un système qui n'a qu'un défenseur apprend à tout justifier. Les deux
échouent de la même manière : leur conclusion est connue d'avance, donc
elle ne porte aucune information.

Ici les deux plaident sur les MÊMES faits mesurés. Ce qui départage n'est
pas une règle fixe, c'est l'historique : chaque argument porte un poids
MESURÉ sur les signaux résolus (`calibrer`). Un argument qui ne discrimine
rien tombe à zéro et disparaît du débat, quel que soit son camp.

Les trois règles qui empêchent ce module d'être une décoration
--------------------------------------------------------------
1. **Un avocat qui plaide toujours ne plaide pas.** Sur un signal propre
   et sans relief, les deux doivent se taire. C'est testé.
2. **Aucun argument n'est une opinion.** Chacun porte le chiffre qui le
   fonde (`mesure`). « je le sens mal » n'est pas un argument.
3. **Asymétrie assumée.** Une base d'information mince peut faire DOUTER,
   jamais RASSURER. Quand la base est faible, la défense ne peut pas
   pousser le facteur au-dessus de 1,0 — le doute, lui, passe.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
N_MIN_ARGUMENT = 25       # sous cet effectif, un argument garde son poids par défaut
POIDS_MIN, POIDS_MAX = 0.0, 2.0
R_REFERENCE = 0.50        # écart de R qui vaut un poids de 1,0
Z_BRUIT = 1.64            # un écart doit dépasser le bruit avant de compter
PLAFOND_R = 10.0          # un gain au-delà vient d'un stop irréaliste, pas d'un edge

SEUIL_BLOCAGE = -0.60     # au-delà, le signal ne sort pas
SEUIL_AFFAIBLI = -0.20
SEUIL_RENFORCE = 0.20
AMPLITUDE = 0.35          # le débat module la conviction de ±35 %, jamais plus

SL_MIN_ATR = 1.0
RR_MIN = 1.5
N_MIN_COMBO = 20


# ==========================================================================
# 1. LA MATIÈRE DU DÉBAT
# ==========================================================================
@dataclass
class Contexte:
    """Tout ce qui est CONNU À L'ÉMISSION. Rien d'autre n'a le droit d'entrer.

    Un argument qui lirait le résultat produirait un débat magnifique et
    parfaitement inutilisable en direct.
    """
    atr: float = 0.0
    spread: float = 0.0
    # --- AG-10 Miroir ---
    score_intermarche: float = 0.0     # −1..+1
    base_intermarche: float = 0.0      # quantité d'information disponible
    base_fiable: bool = False
    # --- AG-11..15 marchés ---
    regime_marche: str = "inconnu"     # haussier | baissier | neutre | inconnu
    instrument_leader: bool = False
    # --- structure ---
    confluence_tf: int = 1             # nb de timeframes d'accord
    # --- calendrier ---
    news_dans_h: float | None = None   # heures avant la prochaine news majeure
    # --- mémoire du superviseur ---
    esperance_combo: float | None = None   # R moyen mesuré sur ce couple
    n_combo: int = 0
    seuil_note_mesure: float | None = None


@dataclass
class Argument:
    code: str        # identifiant STABLE — c'est lui qu'on calibre
    camp: str        # "contre" | "pour"
    texte: str
    mesure: str      # le chiffre qui le fonde
    force: float = 1.0   # 0..1, intensité du fait lui-même
    famille: str = "divers"   # voir FAMILLES — sert à ne pas compter 2× la même chose


# Deux arguments de la même famille disent la MÊME chose avec des mots
# différents. « le marché est haussier » et « l'instrument mène son marché
# haussier » ne sont pas deux preuves : c'en est une, vue deux fois.
# Sans ce regroupement, un avocat bavard gagne toujours — c'est exactement
# le défaut qui avait produit « 16 actifs sur 16 haussiers, score +1,00 ».
FAMILLES = ("geometrie", "intermarche", "regime", "historique",
            "structure", "calendrier")


def rr_effectif(s, ctx: Contexte) -> float:
    """Le R:R qui resterait si le stop était placé honnêtement.

    Un R:R de 3,0 obtenu avec un stop à 0,29 ATR n'existe pas : il suppose
    que le marché respecte une distance plus petite que sa respiration. On
    élargit le stop au minimum, puis on recalcule. Sur le cas cuivre réel,
    3,00 devient 0,86 — et l'argument « R:R généreux » disparaît, ce qui
    est le comportement voulu.
    """
    risque = abs(s.entree - s.sl)
    if ctx.atr > 0:
        risque = max(risque, SL_MIN_ATR * ctx.atr)
    if ctx.spread > 0:
        risque = max(risque, 2 * ctx.spread)
    return abs(s.tp - s.entree) / risque if risque else 0.0


@dataclass
class Verdict:
    verdict: str                 # BLOQUÉ | AFFAIBLI | NEUTRE | RENFORCÉ
    score: float                 # −1..+1
    facteur: float               # multiplicateur de conviction
    contre: list[Argument] = field(default_factory=list)
    pour: list[Argument] = field(default_factory=list)
    fiable: bool = True
    explication: str = ""

    @property
    def bloque(self) -> bool:
        return self.verdict == "BLOQUÉ"

    @property
    def muet(self) -> bool:
        """Les deux avocats se sont tus. C'est un résultat, pas une panne."""
        return not self.contre and not self.pour


# ==========================================================================
# 2. AG-16 — L'AVOCAT DU DIABLE
# ==========================================================================
def plaider_contre(s, ctx: Contexte) -> list[Argument]:
    """Il ne cherche pas des raisons de refuser : il cherche les FAITS qui,
    historiquement, précèdent une perte. La différence est toute la valeur
    de l'agent."""
    out: list[Argument] = []

    # --- le stop est-il dans le bruit ? (1re cause des 220 SL) ----------
    if ctx.atr > 0:
        d = abs(s.entree - s.sl) / ctx.atr
        if d < SL_MIN_ATR:
            out.append(Argument(
                "stop_dans_le_bruit", "contre",
                "le stop est à l'intérieur du bruit du marché",
                f"{d:.2f} ATR (minimum {SL_MIN_ATR:.1f})",
                force=min(1.0, (SL_MIN_ATR - d) / SL_MIN_ATR),
                famille="geometrie"))

    if ctx.spread > 0 and abs(s.entree - s.sl) < 2 * ctx.spread:
        out.append(Argument(
            "stop_sous_le_spread", "contre",
            "le spread seul peut déclencher le stop",
            f"risque {abs(s.entree - s.sl):.5f} vs spread {ctx.spread:.5f}",
            famille="geometrie"))

    # --- la géométrie tient-elle ? ---------------------------------------
    rr = rr_effectif(s, ctx)
    if 0 < rr < RR_MIN:
        nominal = s.rr
        detail = f"R:R {rr:.2f} (minimum {RR_MIN:.1f})"
        if nominal - rr > 0.3:
            detail += f" — affiché {nominal:.2f}, mais avec un stop irréaliste"
        out.append(Argument(
            "rr_insuffisant", "contre",
            "le rapport gain/risque ne couvre pas le taux de réussite",
            detail, force=min(1.0, (RR_MIN - rr) / RR_MIN),
            famille="geometrie"))

    # --- le reste du marché dit-il le contraire ? ------------------------
    if ctx.score_intermarche < -0.20:
        out.append(Argument(
            "miroir_contredit", "contre",
            "les actifs corrélés vont dans l'autre sens",
            f"score intermarché {ctx.score_intermarche:+.2f}",
            force=min(1.0, abs(ctx.score_intermarche)), famille="intermarche"))

    # --- la base d'information est-elle mince ? --------------------------
    # Asymétrie : ceci fait douter. Le symétrique n'existe pas.
    if not ctx.base_fiable and ctx.base_intermarche > 0:
        out.append(Argument(
            "base_mince", "contre",
            "trop peu d'information corrélée pour se prononcer",
            f"base {ctx.base_intermarche:.2f}", force=0.5, famille="intermarche"))

    # --- ce couple a-t-il déjà prouvé qu'il perdait ? --------------------
    if ctx.n_combo >= N_MIN_COMBO and ctx.esperance_combo is not None \
            and ctx.esperance_combo < -0.10:
        out.append(Argument(
            "combo_negatif", "contre",
            f"ce couple {s.instrument}×{s.tf} perd de l'argent depuis le début",
            f"{ctx.esperance_combo:+.2f}R sur {ctx.n_combo} signaux",
            force=min(1.0, abs(ctx.esperance_combo)), famille="historique"))

    # --- le signal va-t-il contre son propre marché ? --------------------
    contraire = (s.sens == "achat" and ctx.regime_marche == "baissier") or \
                (s.sens == "vente" and ctx.regime_marche == "haussier")
    if contraire:
        out.append(Argument(
            "contre_le_regime", "contre",
            "le signal va contre le régime mesuré de son marché",
            f"marché {ctx.regime_marche}, signal {s.sens}", force=0.7,
            famille="regime"))

    # --- une news va-t-elle effacer l'analyse technique ? ----------------
    if ctx.news_dans_h is not None and 0 <= ctx.news_dans_h <= 2:
        out.append(Argument(
            "news_imminente", "contre",
            "une publication majeure tombe avant l'horizon du trade",
            f"dans {ctx.news_dans_h:.1f} h",
            force=1.0 - ctx.news_dans_h / 2, famille="calendrier"))

    # --- la note passe-t-elle le seuil MESURÉ (pas deviné) ? -------------
    if ctx.seuil_note_mesure is not None and s.note < ctx.seuil_note_mesure:
        out.append(Argument(
            "sous_le_seuil_mesure", "contre",
            "la note est sous le seuil qui maximise le R total",
            f"note {s.note:.0%} vs seuil {ctx.seuil_note_mesure:.0%}",
            force=min(1.0, (ctx.seuil_note_mesure - s.note) * 3),
            famille="historique"))

    return out


# ==========================================================================
# 3. AG-18 — L'AVOCAT DE LA DÉFENSE
# ==========================================================================
def plaider_pour(s, ctx: Contexte) -> list[Argument]:
    """Symétrique d'AG-16, avec une contrainte de plus : il n'a le droit de
    parler que de faits POSITIVEMENT mesurés. « rien ne s'oppose » n'est pas
    un argument pour — c'est une absence d'argument contre."""
    out: list[Argument] = []

    # --- stop hors du bruit : le sous-ensemble le plus rentable ----------
    if ctx.atr > 0:
        d = abs(s.entree - s.sl) / ctx.atr
        if d >= 1.5:
            out.append(Argument(
                "stop_hors_bruit", "pour",
                "le stop est franchement hors du bruit : une invalidation réelle",
                f"{d:.2f} ATR", force=min(1.0, (d - 1.5) / 1.5 + 0.5),
                famille="geometrie"))

    # --- géométrie généreuse ---------------------------------------------
    # ⚠️ On plaide le R:R EFFECTIF, jamais l'affiché. Sinon la défense
    # s'appuie sur un stop que l'accusation vient de démonter.
    rr = rr_effectif(s, ctx)
    if rr >= 2.5:
        out.append(Argument(
            "rr_genereux", "pour",
            "le rapport gain/risque laisse de la marge au taux de réussite",
            f"R:R {rr:.2f} — équilibre à {1 / (1 + rr):.0%}",
            force=min(1.0, (rr - 2.5) / 2.5 + 0.4), famille="geometrie"))

    # --- le reste du marché confirme — ET la base est fiable -------------
    # L'exigence de fiabilité n'existe QUE de ce côté. C'est l'asymétrie.
    if ctx.score_intermarche > 0.20 and ctx.base_fiable:
        out.append(Argument(
            "miroir_confirme", "pour",
            "les actifs corrélés vont dans le même sens, sur une base solide",
            f"score {ctx.score_intermarche:+.2f} · base {ctx.base_intermarche:.2f}",
            force=min(1.0, ctx.score_intermarche), famille="intermarche"))

    # --- ce couple a déjà prouvé qu'il gagnait --------------------------
    if ctx.n_combo >= N_MIN_COMBO and ctx.esperance_combo is not None \
            and ctx.esperance_combo > 0.10:
        out.append(Argument(
            "combo_positif", "pour",
            f"ce couple {s.instrument}×{s.tf} gagne de l'argent depuis le début",
            f"{ctx.esperance_combo:+.2f}R sur {ctx.n_combo} signaux",
            force=min(1.0, ctx.esperance_combo), famille="historique"))

    # --- le signal va dans le sens de son marché -------------------------
    aligne = (s.sens == "achat" and ctx.regime_marche == "haussier") or \
             (s.sens == "vente" and ctx.regime_marche == "baissier")
    if aligne:
        out.append(Argument(
            "avec_le_regime", "pour",
            "le signal va dans le sens du régime mesuré de son marché",
            f"marché {ctx.regime_marche}, signal {s.sens}", force=0.6,
            famille="regime"))

    # --- l'instrument entraîne son marché au lieu de le suivre -----------
    if ctx.instrument_leader:
        out.append(Argument(
            "instrument_leader", "pour",
            "l'instrument mène son marché — il informe au lieu de suivre",
            "leader mesuré sur 250 séances", force=0.5, famille="regime"))

    # --- plusieurs échelles de temps disent la même chose ----------------
    if ctx.confluence_tf >= 3:
        out.append(Argument(
            "confluence", "pour",
            "plusieurs échelles de temps concordent",
            f"{ctx.confluence_tf} timeframes alignés",
            force=min(1.0, (ctx.confluence_tf - 2) / 3), famille="structure"))

    return out


# ==========================================================================
# 4. LE DÉBAT
# ==========================================================================
def debat(s, ctx: Contexte, poids: dict[str, float] | None = None) -> Verdict:
    """Confronte les deux plaidoiries et rend un facteur de conviction.

    `poids` vient de `calibrer()`. Absent, chaque argument vaut 1,0 —
    c'est-à-dire qu'on n'a encore rien mesuré, et le module le dit.
    """
    p = poids or {}
    contre = plaider_contre(s, ctx)
    pour = plaider_pour(s, ctx)

    def total(args: list[Argument]) -> float:
        """Une famille = une voix, celle de son argument le plus fort.

        Additionner « le marché est haussier », « l'instrument mène ce
        marché haussier » et « le régime est haussier » reviendrait à
        compter trois fois la même observation. C'est le défaut qui a
        produit un jour « 16 sur 16, score +1,00 » : une unanimité fabriquée
        par la redondance, pas par les faits.
        """
        par_famille: dict[str, float] = {}
        for a in args:
            v = a.force * p.get(a.code, 1.0)
            par_famille[a.famille] = max(par_famille.get(a.famille, 0.0), v)
        return sum(par_famille.values())

    t_contre, t_pour = total(contre), total(pour)
    brut = t_pour - t_contre
    # Compression douce : trois arguments moyens ne valent pas trois fois un.
    score = max(-1.0, min(1.0, brut / (1.0 + abs(brut))))

    fiable = ctx.base_fiable or ctx.n_combo >= N_MIN_COMBO
    facteur = 1.0 + AMPLITUDE * score
    if not fiable:
        # Une base mince peut faire douter, jamais rassurer.
        facteur = min(1.0, facteur)

    if score <= SEUIL_BLOCAGE:
        v = "BLOQUÉ"
    elif score <= SEUIL_AFFAIBLI:
        v = "AFFAIBLI"
    elif score >= SEUIL_RENFORCE and fiable:
        v = "RENFORCÉ"
    else:
        v = "NEUTRE"

    if not contre and not pour:
        expl = "aucun des deux avocats n'a trouvé de fait à plaider"
    else:
        f_c = len({a.famille for a in contre})
        f_p = len({a.famille for a in pour})
        expl = (f"{len(contre)} objection(s) sur {f_c} famille(s) · "
                f"{len(pour)} argument(s) en faveur sur {f_p} famille(s)")
        if not fiable and t_pour > t_contre:
            expl += " — défense plafonnée : base d'information insuffisante"

    return Verdict(v, round(score, 3), round(facteur, 3), contre, pour,
                   fiable, expl)


# ==========================================================================
# 5. CALIBRATION — c'est ici que les avocats apprennent
# ==========================================================================
@dataclass
class PoidsArgument:
    code: str
    camp: str
    poids: float
    n_present: int
    r_present: float
    r_absent: float
    verdict: str          # "discriminant" | "inutile" | "à retourner"


def calibrer(paires: list[tuple]) -> dict[str, PoidsArgument]:
    """Mesure ce que chaque argument vaut RÉELLEMENT.

    `paires` : liste de (Signal résolu, Contexte à l'émission).

    Pour chaque argument : le R moyen quand il est présent, contre le R
    moyen quand il est absent. Un argument « contre » qui ne fait pas
    baisser le R ne sert à rien — même s'il a l'air intelligent. Un
    argument qui fait l'INVERSE de ce qu'il prétend est signalé pour être
    retourné, pas supprimé : c'est un contre-indicateur, donc une
    information.

    Sous `N_MIN_ARGUMENT` observations, le poids reste à 1,0. On ne
    recalibre pas un agent sur douze trades.
    """
    r_par_code: dict[str, list[float]] = defaultdict(list)
    camp_par_code: dict[str, str] = {}
    tous: list[float] = []

    for s, ctx in paires:
        if not s.resolu or s.r_realise is None:
            continue
        # Plafond : un signal dont le stop était à 0,08 ATR affiche un R:R
        # nominal de 75. S'il gagne une fois, sa moyenne écrase 120 trades
        # et décide seule du poids d'un argument. Ce gain n'est pas un edge,
        # c'est un artefact de géométrie — on le borne.
        r = max(-PLAFOND_R, min(PLAFOND_R, s.r_realise))
        tous.append(r)
        for a in plaider_contre(s, ctx) + plaider_pour(s, ctx):
            camp_par_code[a.code] = a.camp
            r_par_code[a.code].append(r)

    out: dict[str, PoidsArgument] = {}
    n_total = len(tous)
    somme = sum(tous)
    carres = sum(x * x for x in tous)

    for code, rs in r_par_code.items():
        n = len(rs)
        s_p = sum(rs)
        r_pres = s_p / n
        n_abs = n_total - n
        r_abs = (somme - s_p) / n_abs if n_abs else 0.0
        camp = camp_par_code[code]

        # Un argument CONTRE est utile s'il fait baisser le R.
        # Un argument POUR est utile s'il le fait monter.
        discrimination = (r_abs - r_pres) if camp == "contre" else (r_pres - r_abs)

        # Le bruit. Avec 60 trades et des R très dispersés, un écart de
        # 0,3R apparaît tout seul. Sans cette borne, le module donnerait du
        # poids à un argument tiré à pile ou face — c'est exactement le
        # piège du lead-lag corrigé dans agents_marches.py.
        v_p = max(0.0, sum(x * x for x in rs) / n - r_pres ** 2)
        v_a = max(0.0, (carres - sum(x * x for x in rs)) / n_abs - r_abs ** 2) \
            if n_abs else 0.0
        erreur = (v_p / n + (v_a / n_abs if n_abs else 0.0)) ** 0.5
        marge = Z_BRUIT * erreur

        if n < N_MIN_ARGUMENT:
            poids, verdict = 1.0, "non mesuré"
        elif discrimination <= -marge:
            poids, verdict = POIDS_MIN, "à retourner"
        elif discrimination <= marge:
            poids, verdict = POIDS_MIN, "inutile"
        else:
            poids = max(POIDS_MIN, min(POIDS_MAX, discrimination / R_REFERENCE))
            verdict = "discriminant"

        out[code] = PoidsArgument(code, camp, round(poids, 3), n,
                                  round(r_pres, 3), round(r_abs, 3), verdict)
    return out


def rapport_calibration(poids: dict[str, PoidsArgument]) -> str:
    if not poids:
        return "Aucun argument observé — rien à calibrer.\n"
    l = ["# Calibration du débat contradictoire", "",
         "| argument | camp | n | R présent | R absent | poids | verdict |",
         "|---|---|---:|---:|---:|---:|---|"]
    for p in sorted(poids.values(), key=lambda x: -x.poids):
        l.append(f"| {p.code} | {p.camp} | {p.n_present} | {p.r_present:+.2f} "
                 f"| {p.r_absent:+.2f} | {p.poids:.2f} | {p.verdict} |")
    retourner = [p.code for p in poids.values() if p.verdict == "à retourner"]
    inutiles = [p.code for p in poids.values() if p.verdict == "inutile"]
    l += ["", f"**{sum(1 for p in poids.values() if p.verdict == 'discriminant')} "
              f"argument(s) discriminant(s)** sur {len(poids)}."]
    if retourner:
        l.append(f"\n⚠️ **À retourner** (ils prédisent l'inverse de ce qu'ils "
                 f"affirment, donc ils portent de l'information) : "
                 f"{', '.join(retourner)}")
    if inutiles:
        l.append(f"\nSans pouvoir discriminant, poids mis à zéro : "
                 f"{', '.join(inutiles)}")
    return "\n".join(l) + "\n"


# ==========================================================================
def positions_graphe(v: Verdict) -> dict[str, str]:
    """Traduit le débat en positions affichables sur le graphe.

    "pour" (vert) · "contre" (rouge) · "neutre" (gris). Un avocat muet est
    NEUTRE, pas absent : son silence est une information."""
    return {"AG-16": "contre" if v.contre else "neutre",
            "AG-18": "pour" if v.pour else "neutre"}


# --------------------------------------------------------------------------
def _demo() -> None:
    from dataclasses import dataclass as _dc

    @_dc
    class S:
        id: str; instrument: str; tf: str; sens: str
        entree: float; sl: float; tp: float; note: float
        statut: str = "en_attente"
        @property
        def rr(self):
            r = abs(self.entree - self.sl)
            return abs(self.tp - self.entree) / r if r else 0.0
        @property
        def resolu(self): return self.statut in ("TP", "SL")
        @property
        def r_realise(self):
            return self.rr if self.statut == "TP" else -1.0 if self.statut == "SL" else None

    cas = [
        ("CUIVRE M5 — le cas réel du 16/09",
         S("1", "CUIVRE", "M5", "achat", 6.50, 6.49, 6.53, 0.31),
         Contexte(atr=0.035, spread=0.003, score_intermarche=-0.45,
                  base_intermarche=2.28, base_fiable=True,
                  regime_marche="baissier", n_combo=34, esperance_combo=-0.38)),
        ("XAU/USD H1 — un setup propre",
         S("2", "XAUUSD", "H1", "achat", 2400.0, 2380.0, 2455.0, 0.62),
         Contexte(atr=12.0, spread=0.3, score_intermarche=0.52,
                  base_intermarche=4.10, base_fiable=True,
                  regime_marche="haussier", instrument_leader=True,
                  confluence_tf=3, n_combo=41, esperance_combo=0.22)),
        ("EUR/USD M15 — rien à dire, ni pour ni contre",
         S("3", "EURUSD", "M15", "achat", 1.0850, 1.0830, 1.0894, 0.50),
         Contexte(atr=0.0018, spread=0.00008, score_intermarche=0.05,
                  base_intermarche=1.2, base_fiable=True,
                  regime_marche="neutre", n_combo=25, esperance_combo=0.0)),
    ]

    for titre, s, ctx in cas:
        v = debat(s, ctx)
        print(f"\n{'=' * 74}\n  {titre}\n{'=' * 74}")
        print(f"  {v.verdict}   score {v.score:+.2f}   "
              f"conviction × {v.facteur:.2f}")
        print(f"  {v.explication}")
        for a in v.contre:
            print(f"    😈 CONTRE  {a.texte}\n               → {a.mesure}")
        for a in v.pour:
            print(f"    🛡️  POUR    {a.texte}\n               → {a.mesure}")
        if v.muet:
            print("    (les deux avocats se taisent — c'est un résultat)")
        print(f"    graphe : {positions_graphe(v)}")


if __name__ == "__main__":
    _demo()
