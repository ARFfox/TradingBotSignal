#!/usr/bin/env python3
"""
AG-11..14 AGENTS DE MARCHE + AG-15 MATRICE INTERMARCHES.

    python3 agents_marches.py          # demonstration sur donnees reelles

Quatre agents, un par marche : FOREX, CRYPTO, MATIERES, ACTIONS.
Plus un cinquieme qui analyse les relations ENTRE les quatre.

Choix d'architecture
--------------------
Une SEULE classe AgentMarche, instanciee quatre fois. Ecrire quatre classes
quasi identiques garantit qu'elles divergeront : une correction appliquee au
crypto et oubliee sur le forex, et le systeme ment sur un marche sans que
personne ne le voie. Ce qui change d'un marche a l'autre, ce sont des
DONNEES (univers, pivot, calendrier), pas du code.

Aucun appel reseau : on injecte un DataFrame de prix. C'est ce qui rend
l'ensemble testable sans internet.

Ce que chaque agent de marche mesure
------------------------------------
  largeur     % de membres haussiers — un marche qui monte a 3 actifs sur 30
              n'est pas un marche haussier, c'est trois actifs haussiers
  cohesion    correlation moyenne entre membres — le marche bouge-t-il en bloc ?
  dispersion  ecart-type des performances — y a-t-il de quoi selectionner ?
  leader      le membre qui tire, retardataire celui qui traine
  regime      deduit de largeur + cohesion, jamais ecrit en dur

Ce que la matrice mesure
------------------------
  correlations entre les COMPOSITES des quatre marches
  avance/retard : quel marche bouge en premier (correlation croisee decalee)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Univers. Ce sont des DONNEES : ajouter un actif ne demande aucun code.
# --------------------------------------------------------------------------
MARCHES: dict[str, dict] = {
    "forex": {
        "nom": "Forex", "emoji": "💱", "coul": "#58a6ff", "pivot": "DX-Y.NYB",
        "tickers": ["EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "USDCHF=X",
                    "USDJPY=X", "USDCAD=X", "EURJPY=X", "EURGBP=X", "DX-Y.NYB"],
    },
    "crypto": {
        "nom": "Crypto", "emoji": "🪙", "coul": "#f0b90b", "pivot": "BTC-USD",
        "tickers": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
                    "ADA-USD", "AVAX-USD", "LINK-USD", "DOT-USD", "MATIC-USD"],
    },
    "matieres": {
        "nom": "Matières premières", "emoji": "🥇", "coul": "#e3b341", "pivot": "GC=F",
        "tickers": ["GC=F", "SI=F", "PL=F", "PA=F", "HG=F", "CL=F", "BZ=F",
                    "NG=F", "ZC=F", "ZW=F"],
    },
    "actions": {
        "nom": "Actions", "emoji": "📈", "coul": "#3fb950", "pivot": "SPY",
        "tickers": ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "GOOGL",
                    "AMZN", "META", "TSLA", "XLE", "XLF"],
    },
}

# Parametres — memes principes que constellation_agent.py
FENETRE_PERF = 20          # jours pour la performance et la dispersion
FENETRE_COHESION = 90      # jours pour la correlation moyenne interne
MEMBRES_MIN = 3            # sous ce nombre, on ne conclut rien
LAGS = range(-5, 6)        # avance/retard teste sur +/- 5 jours
LAG_MIN_GAIN = 0.05        # gain de correlation exige pour affirmer une avance
# Seuil de significativite. On teste 11 decalages : au seuil nominal de 5 %,
# un maximum apparait par pur hasard dans ~43 % des cas. Le z de 2,8 corrige
# ce test multiple (Bonferroni sur 11). Sans lui, le module affirme des
# avances inexistantes — verifie : sur un jeu ou une seule avance etait
# injectee, il en annoncait deux.
Z_SIGNIFICATIF = 2.8


# --------------------------------------------------------------------------
@dataclass
class Carreau:
    """Une case de la grille — ce que l'interface affiche par actif."""
    ticker: str
    marche: str
    variation_pct: float       # performance sur FENETRE_PERF
    biais: str                 # haussier | baissier | neutre
    force_relative: float      # performance moins la mediane du marche
    role: str                  # leader | retardataire | ""


@dataclass
class EtatMarche:
    """Le verdict d'un agent de marche."""
    cle: str
    nom: str
    emoji: str
    coul: str
    membres: int
    largeur: float             # 0..1 — part de membres haussiers
    cohesion: float            # -1..1 — correlation moyenne interne
    dispersion: float          # ecart-type des performances
    variation_pct: float       # performance du composite
    regime: str
    leader: str
    retardataire: str
    carreaux: list[Carreau] = field(default_factory=list)
    fiable: bool = True
    note: str = ""

    def resume(self) -> str:
        if not self.fiable:
            return f"{self.emoji} {self.nom} — {self.note}"
        return (f"{self.emoji} {self.nom} : {self.regime} · "
                f"largeur {self.largeur:.0%} · cohésion {self.cohesion:+.2f} · "
                f"{self.variation_pct:+.1f}% · leader {self.leader}")


# --------------------------------------------------------------------------
def _rendements(prix: pd.DataFrame, calendrier: pd.Index | None = None) -> pd.DataFrame:
    """Log-rendements. Si un calendrier est fourni, on s'y aligne — meme
    methode que la constellation : sans ca, melanger crypto 7j/7 et actions
    5j/7 detruit les correlations."""
    p = prix.ffill()
    if calendrier is not None:
        p = p.loc[p.index.intersection(calendrier)]
    return np.log(p / p.shift(1)).replace([np.inf, -np.inf], np.nan).iloc[1:]


def _biais(serie: pd.Series) -> str:
    """Biais auto-calibre sur l'actif lui-meme (voir constellation_agent)."""
    s = serie.dropna()
    if len(s) < 60:
        return "neutre"
    e20, e50 = s.ewm(span=20).mean(), s.ewm(span=50).mean()
    ec = (e20 - e50) / e50
    sigma = float(ec.tail(250).std())
    if not np.isfinite(sigma) or sigma == 0:
        return "neutre"
    z = float(ec.iloc[-1]) / sigma
    return "haussier" if z > 0.5 else "baissier" if z < -0.5 else "neutre"


# --------------------------------------------------------------------------
class AgentMarche:
    """AG-11 Forex · AG-12 Crypto · AG-13 Matières · AG-14 Actions.

    Une classe, quatre instances. Ce qui differe est dans MARCHES.
    """

    def __init__(self, cle: str, prix: pd.DataFrame):
        if cle not in MARCHES:
            raise ValueError(f"marché inconnu : {cle}")
        self.cle = cle
        self.cfg = MARCHES[cle]
        self.tickers = [t for t in self.cfg["tickers"] if t in prix.columns]
        self.prix = prix[self.tickers] if self.tickers else pd.DataFrame()
        self._etat: EtatMarche | None = None

    # -- composite ---------------------------------------------------------
    def composite(self) -> pd.Series:
        """Rendement moyen equipondere du marche.

        Equipondere et non pondere par capitalisation : on mesure ici le
        COMPORTEMENT du marche, pas sa valeur. Une ponderation par taille
        ferait dire au composite actions ce que fait Nvidia.
        """
        r = _rendements(self.prix)
        if r.empty:
            return pd.Series(dtype=float)
        return r.mean(axis=1, skipna=True).dropna()

    # -- verdict -----------------------------------------------------------
    def etat(self) -> EtatMarche:
        if self._etat is not None:
            return self._etat

        c = self.cfg
        vide = EtatMarche(cle=self.cle, nom=c["nom"], emoji=c["emoji"],
                          coul=c["coul"], membres=len(self.tickers),
                          largeur=0.0, cohesion=0.0, dispersion=0.0,
                          variation_pct=0.0, regime="indéterminé",
                          leader="—", retardataire="—", fiable=False,
                          note=f"{len(self.tickers)} membre(s) — données insuffisantes")
        if len(self.tickers) < MEMBRES_MIN:
            self._etat = vide
            return vide

        r = _rendements(self.prix)
        if len(r) < FENETRE_PERF + 5:
            self._etat = vide
            return vide

        # Performance de chaque membre sur la fenetre.
        perf = (np.exp(r.tail(FENETRE_PERF).sum(skipna=True)) - 1) * 100
        perf = perf[perf.notna()]
        if perf.empty:
            self._etat = vide
            return vide

        biais = {t: _biais(self.prix[t]) for t in perf.index}
        haussiers = sum(1 for b in biais.values() if b == "haussier")
        baissiers = sum(1 for b in biais.values() if b == "baissier")
        largeur = haussiers / len(biais)

        # Cohesion : correlation moyenne des paires (hors diagonale).
        cm = r.tail(FENETRE_COHESION).corr(min_periods=30)
        masque = ~np.eye(len(cm), dtype=bool)
        cohesion = float(np.nanmean(cm.values[masque])) if len(cm) > 1 else 0.0

        mediane = float(perf.median())
        dispersion = float(perf.std())
        leader = str(perf.idxmax())
        retardataire = str(perf.idxmin())

        carreaux = [
            Carreau(ticker=t, marche=self.cle, variation_pct=round(float(v), 2),
                    biais=biais[t], force_relative=round(float(v) - mediane, 2),
                    role="leader" if t == leader else
                         "retardataire" if t == retardataire else "")
            for t, v in perf.sort_values(ascending=False).items()
        ]

        comp = self.composite()
        var = (np.exp(comp.tail(FENETRE_PERF).sum()) - 1) * 100

        self._etat = EtatMarche(
            cle=self.cle, nom=c["nom"], emoji=c["emoji"], coul=c["coul"],
            membres=len(perf), largeur=round(largeur, 3),
            cohesion=round(cohesion, 3), dispersion=round(dispersion, 2),
            variation_pct=round(float(var), 2),
            regime=self._regime(largeur, baissiers / len(biais), cohesion),
            leader=leader, retardataire=retardataire, carreaux=carreaux)
        return self._etat

    @staticmethod
    def _regime(largeur: float, part_baissiere: float, cohesion: float) -> str:
        """Le regime se DEDUIT des mesures, il n'est jamais ecrit en dur.

        La cohesion compte autant que la direction : un marche qui monte en
        bloc (cohesion elevee) est un marche a un seul facteur — on y joue
        la direction. Un marche qui monte en ordre disperse offre de la
        selection, et une confirmation intermarche y vaut beaucoup moins.
        """
        if cohesion >= 0.60:
            bloc = "en bloc"
        elif cohesion >= 0.30:
            bloc = "groupé"
        else:
            bloc = "dispersé"

        if largeur >= 0.70:
            sens = "haussier large"
        elif largeur >= 0.55:
            sens = "haussier"
        elif part_baissiere >= 0.70:
            sens = "baissier large"
        elif part_baissiere >= 0.55:
            sens = "baissier"
        else:
            sens = "sans direction"
        return f"{sens}, {bloc}"

    # -- pour l'interface --------------------------------------------------
    def carte_agent(self, code: str) -> dict:
        """Au format exact des cartes de tableau.agents_live()."""
        e = self.etat()
        if not e.fiable:
            lignes, conviction, statut = [e.note], 50, "INITIALISATION"
        else:
            lignes = [
                f"{e.regime} · {e.membres} actifs",
                f"largeur {e.largeur:.0%} haussiers · cohésion {e.cohesion:+.2f}",
                f"leader {e.leader} · retardataire {e.retardataire}",
            ]
            # Conviction = ecart a 50 %, dans les deux sens : un marche
            # franchement baissier est une conviction, pas une absence.
            conviction = round(abs(e.largeur - 0.5) * 2 * 100)
            statut = "STREAMING"
        return {"code": code, "nom": e.nom, "emoji": e.emoji,
                "role": f"Marché {e.nom.lower()} — largeur · cohésion · rotation",
                "coul": e.coul, "statut": statut, "activites": lignes,
                "conviction": conviction,
                "metriques": f"{e.membres} actifs · fenêtre {FENETRE_PERF} j · "
                             f"dispersion {e.dispersion:.1f}"}


# --------------------------------------------------------------------------
class MatriceMarches:
    """AG-15 — les relations ENTRE les quatre marches.

    Deux mesures, et la seconde est celle qui a de la valeur :

    1. CORRELATION entre composites : les marches bougent-ils ensemble ?
    2. AVANCE / RETARD : lequel bouge en PREMIER ? On decale une serie de
       -5 a +5 jours et on garde le decalage qui maximise la correlation.
       Un marche qui avance sur un autre de facon stable donne une lecture
       en avance sur ce dernier.

    Prudence obligatoire sur le point 2 : sur des donnees quotidiennes et
    des marches liquides, l'avance reelle est le plus souvent NULLE. Une
    avance affichee sans marge nette est du bruit, et parier dessus coute
    cher. D'ou LAG_MIN_GAIN : on n'affirme une avance que si elle bat le
    decalage zero d'une marge franche.
    """

    def __init__(self, prix: pd.DataFrame):
        self.prix = prix
        self.agents = {k: AgentMarche(k, prix) for k in MARCHES}
        self._comp: pd.DataFrame | None = None

    def composites(self) -> pd.DataFrame:
        if self._comp is None:
            d = {k: a.composite() for k, a in self.agents.items()}
            self._comp = pd.DataFrame({k: v for k, v in d.items() if not v.empty})
        return self._comp

    def correlations(self, fenetre: int = 90) -> pd.DataFrame:
        c = self.composites()
        if c.shape[1] < 2:
            return pd.DataFrame()
        return c.tail(fenetre).corr(min_periods=30)

    def avance_retard(self, fenetre: int = 250) -> list[dict]:
        """Pour chaque paire : qui bouge en premier, et de combien."""
        c = self.composites().tail(fenetre)
        out = []
        cles = list(c.columns)
        for i, a in enumerate(cles):
            for b in cles[i + 1:]:
                sa, sb = c[a], c[b]
                scores = {}
                for k in LAGS:
                    v = sa.corr(sb.shift(k))
                    if pd.notna(v):
                        scores[k] = float(v)
                if not scores:
                    continue
                meilleur = max(scores, key=lambda k: abs(scores[k]))
                base = abs(scores.get(0, 0.0))
                gain = abs(scores[meilleur]) - base

                # Une correlation doit d'abord exister avant de mener.
                n_obs = int(min(sa.notna().sum(), sb.notna().sum()))
                seuil = Z_SIGNIFICATIF / np.sqrt(max(n_obs, 30))
                significatif = abs(scores[meilleur]) >= seuil

                if meilleur == 0 or gain < LAG_MIN_GAIN or not significatif:
                    verdict, jours, meneur = "simultané", 0, "—"
                else:
                    # corr(a_t, b_{t-k}) maximal pour k>0 : le passe de b
                    # explique le present de a, donc b mene.
                    meneur = b if meilleur > 0 else a
                    jours = abs(meilleur)
                    verdict = f"{meneur} mène de {jours} j"
                out.append({"a": a, "b": b, "corr": round(scores.get(0, 0.0), 3),
                            "meneur": meneur, "jours": jours, "verdict": verdict,
                            "gain": round(gain, 3), "seuil": round(float(seuil), 3),
                            "corr_max": round(scores[meilleur], 3)})
        return out

    def graphe(self, seuil: float = 0.20) -> dict:
        """Noeuds et liens pour une vue en graphe (style Obsidian).

        Un lien n'apparait que si |corr| >= seuil : un graphe ou tout est
        relie a tout ne montre rien.
        """
        etats = {k: a.etat() for k, a in self.agents.items()}
        noeuds = [{"id": k, "nom": e.nom, "emoji": e.emoji, "coul": e.coul,
                   "taille": e.membres, "regime": e.regime,
                   "variation_pct": e.variation_pct, "largeur": e.largeur}
                  for k, e in etats.items()]

        cm = self.correlations()
        lag = {(d["a"], d["b"]): d for d in self.avance_retard()}
        liens = []
        if not cm.empty:
            cles = list(cm.columns)
            for i, a in enumerate(cles):
                for b in cles[i + 1:]:
                    v = cm.at[a, b]
                    if pd.isna(v) or abs(v) < seuil:
                        continue
                    d = lag.get((a, b), {})
                    liens.append({"de": a, "vers": b, "corr": round(float(v), 3),
                                  "sens": "positif" if v > 0 else "négatif",
                                  "meneur": d.get("meneur", "—"),
                                  "jours": d.get("jours", 0),
                                  "epaisseur": round(abs(float(v)), 3)})
        return {"noeuds": noeuds, "liens": liens}

    def tuiles(self) -> list[dict]:
        """Les 4 tuiles de marche du niveau 1 de l'interface."""
        out = []
        for k, a in self.agents.items():
            e = a.etat()
            out.append({"cle": k, "nom": e.nom, "emoji": e.emoji, "coul": e.coul,
                        "actifs": e.membres, "variation_pct": e.variation_pct,
                        "largeur": e.largeur, "regime": e.regime,
                        "cohesion": e.cohesion, "leader": e.leader,
                        "fiable": e.fiable})
        return out

    def carte_agent(self, code: str = "AG-15") -> dict:
        cm = self.correlations()
        lignes = []
        if not cm.empty:
            paires = []
            cles = list(cm.columns)
            for i, a in enumerate(cles):
                for b in cles[i + 1:]:
                    v = cm.at[a, b]
                    if pd.notna(v):
                        paires.append((abs(float(v)), a, b, float(v)))
            for _, a, b, v in sorted(paires, reverse=True)[:3]:
                lignes.append(f"{a} ↔ {b} : {v:+.2f}")
        menes = [d for d in self.avance_retard() if d["meneur"] != "—"]
        lignes.append(f"{len(menes)} avance(s) détectée(s)" if menes
                      else "aucune avance nette — marchés simultanés")
        for d in menes[:2]:
            lignes.append(f"{d['verdict']} (gain {d['gain']:+.2f})")
        return {"code": code, "nom": "Intermarchés", "emoji": "🕸️",
                "role": "Relations entre les 4 marchés — corrélation · avance",
                "coul": "#f778ba", "statut": "STREAMING" if not cm.empty else "INITIALISATION",
                "activites": lignes or ["en attente de données"],
                "conviction": round(float(np.nanmean(np.abs(cm.values[~np.eye(len(cm), dtype=bool)]))) * 100)
                              if len(cm) > 1 else 0,
                "metriques": f"{len(cm)} marchés · fenêtre 90 j · décalages ±5 j"}


# --------------------------------------------------------------------------
CODES = {"forex": "AG-11", "crypto": "AG-12", "matieres": "AG-13", "actions": "AG-14"}


def _demo() -> None:
    import warnings
    warnings.filterwarnings("ignore")
    try:
        import yfinance as yf
    except ImportError:
        print("pip3 install yfinance pandas numpy")
        return

    tickers = sorted({t for m in MARCHES.values() for t in m["tickers"]})
    print(f"Téléchargement de {len(tickers)} actifs (2 ans)...")
    d = yf.download(tickers, period="2y", interval="1d",
                    progress=False, auto_adjust=True)["Close"].dropna(axis=1, how="all")
    print(f"OK — {len(d)} lignes, dernière donnée : {d.index[-1].date()}\n")

    m = MatriceMarches(d)
    L = "=" * 76
    print(f"{L}\n  LES QUATRE MARCHÉS\n{L}")
    for k, a in m.agents.items():
        print("  " + a.etat().resume())

    print(f"\n{L}\n  CARREAUX — 5 premiers par marché\n{L}")
    for k, a in m.agents.items():
        e = a.etat()
        if not e.fiable:
            continue
        print(f"\n  {e.emoji} {e.nom}")
        for c in e.carreaux[:5]:
            role = f"  ({c.role})" if c.role else ""
            print(f"    {c.ticker:<12} {c.variation_pct:+7.2f}%  "
                  f"{c.biais:<9} force {c.force_relative:+.2f}{role}")

    print(f"\n{L}\n  RELATIONS ENTRE MARCHÉS\n{L}")
    cm = m.correlations()
    if not cm.empty:
        print(cm.round(2).to_string())
    print()
    for d_ in m.avance_retard():
        print(f"  {d_['a']:<10} ↔ {d_['b']:<10} corr {d_['corr']:+.2f}  "
              f"{d_['verdict']}" + (f"  (gain {d_['gain']:+.2f})" if d_['jours'] else ""))

    print(f"\n{L}\n  GRAPHE\n{L}")
    g = m.graphe()
    print(f"  {len(g['noeuds'])} nœuds, {len(g['liens'])} liens")
    for l in g["liens"]:
        fleche = f"  ({l['meneur']} mène)" if l["jours"] else ""
        print(f"    {l['de']:<10} —— {l['corr']:+.2f} ——> {l['vers']}{fleche}")
    print()


if __name__ == "__main__":
    _demo()
