#!/usr/bin/env python3
"""
AG-09 Constellation + AG-10 Miroir — module de production.

Ce module ne fait AUCUN appel reseau. On lui injecte un DataFrame de prix
(colonnes = tickers, index = dates), il en tire les constellations et le
score intermarche. C'est ce qui le rend testable et branchable sur
n'importe quelle source de feeds/.

API publique
------------
    ag = Constellation(prix)                      # calcul + cache
    ag.groupes("GC=F")                            -> {satellites, miroirs, decouples}
    ag.membres("GC=F")                            -> list[Membre] tries par poids
    ag.ruptures()                                 -> alertes de changement de regime

    miroir = Miroir(ag)
    miroir.evaluer("GC=F", "achat", biais)        -> ScoreIntermarche

Regles gravees dans le code (voir CLAUDE.md) :
  · on correle les RENDEMENTS, jamais les prix
  · le calendrier est aligne sur les jours de cotation du pivot
  · aucune relation n'est ecrite en dur
  · une decision utilise le POIDS CONTINU, jamais une etiquette a seuil
  · une base de confirmation trop mince rend le score neutre, pas optimiste
  · des membres correles entre eux votent UNE fois, pas N fois
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Parametres — calibres sur les donnees reelles du 07/09/2026
# --------------------------------------------------------------------------
FENETRES = {"30j": 30, "90j": 90, "250j": 250}
ORDRE_FEN = list(FENETRES)

SEUIL_SATELLITE = 0.40      # affichage : appartenance au groupe
SEUIL_MIROIR = -0.40
SEUIL_CONFIRMATION = 0.70   # lecture humaine uniquement
COUVERTURE_MIN = 0.60
ECART_STABILITE = 0.35
DERIVE_TRANSITION = 0.25
ARRIVEE_MIN = 0.30

# Decision
# Le blocage se decide sur le score AGREGE, jamais sur un membre isole.
# Une regle "si un membre de poids >= X contredit, on bloque" reintroduit
# exactement la falaise de seuil qu'on cherche a eviter : un poids de 0,599
# passe et 0,601 bloque, alors que rien ne les distingue. Et sur le fond,
# aucun operateur n'annule un achat or parce que le platine hesite pendant
# que l'argent et les mineurs confirment.
SCORE_BLOCAGE = -0.25       # score agrege en dessous duquel le signal tombe
POIDS_NOTABLE = 0.55        # au-dela, une contradiction est signalee (sans bloquer)
SEUIL_REDONDANCE = 0.75     # au-dela, deux membres portent la MEME information
BASE_MINIMALE = 1.00        # somme des poids requise pour que le score compte
AMPLITUDE = 0.35            # facteur de confiance dans [1-A, 1+A]
RECALCUL_H = 6

CACHE = Path.home() / ".constellation_cache.json"


# --------------------------------------------------------------------------
@dataclass
class Membre:
    ticker: str
    corr: float
    corr_30j: float
    corr_90j: float
    corr_250j: float
    stabilite: float
    poids: float                 # |corr| x stabilite — CE QUE LA DECISION UTILISE
    tendance: str                # "-" | "TRANSITION ^" | "TRANSITION v" | "erratique"
    groupe: str                  # "satellite" | "miroir" | "decouple"

    @property
    def sens_attendu(self) -> int:
        """+1 = doit bouger comme le pivot, -1 = a l'oppose, 0 = indifferent."""
        return {"satellite": 1, "miroir": -1}.get(self.groupe, 0)


@dataclass
class ScoreIntermarche:
    score: float                 # [-1, +1]
    facteur_confiance: float     # multiplicateur a appliquer a la confiance
    bloque: bool
    base: float                  # somme des poids ayant vote
    fiable: bool                 # base >= BASE_MINIMALE
    confirment: list[str] = field(default_factory=list)
    contredisent: list[str] = field(default_factory=list)
    ignores: list[str] = field(default_factory=list)
    motif: str = ""

    def resume(self) -> str:
        if self.bloque:
            return f"BLOQUE — {self.motif}"
        base_txt = "" if self.fiable else f" [base mince {self.base:.2f}]"
        txt = (f"score {self.score:+.2f} sur base {self.base:.2f}{base_txt} · "
               f"{len(self.confirment)} confirment, "
               f"{len(self.contredisent)} contredisent · "
               f"confiance x{self.facteur_confiance:.2f}")
        return txt + (f" · {self.motif}" if self.motif else "")


# --------------------------------------------------------------------------
class Constellation:
    """AG-09 — corrélations glissantes, groupes, detection de rupture."""

    def __init__(self, prix: pd.DataFrame, cache: Path | None = CACHE):
        self.prix = prix
        self.cache = cache
        self._tables: dict[str, pd.DataFrame] = {}
        self._ruptures: list[dict] = []
        self._precedent = self._lire_cache()

    # -- calcul ------------------------------------------------------------
    def _rendements(self, pivot: str) -> pd.DataFrame:
        if pivot not in self.prix.columns:
            raise KeyError(f"pivot absent des prix : {pivot}")
        jours = self.prix[pivot].dropna().index
        if len(jours) < 60:
            raise ValueError(f"{pivot} : {len(jours)} jours de cotation, insuffisant")
        aligne = self.prix.ffill().loc[jours]
        r = np.log(aligne / aligne.shift(1))
        return r.replace([np.inf, -np.inf], np.nan).iloc[1:]

    def table(self, pivot: str) -> pd.DataFrame:
        if pivot in self._tables:
            return self._tables[pivot]

        r = self._rendements(pivot)
        colonnes = {}
        for nom, n in FENETRES.items():
            x = r.tail(n)
            x = x[x.columns[x.notna().sum() >= n * COUVERTURE_MIN]]
            if pivot not in x.columns or x.shape[1] < 2:
                continue
            colonnes[nom] = x.corr(min_periods=int(n * 0.5))[pivot]

        if not colonnes:
            self._tables[pivot] = pd.DataFrame()
            return self._tables[pivot]

        t = pd.DataFrame(colonnes)
        for nom in ORDRE_FEN:
            if nom not in t.columns:
                t[nom] = np.nan
        t = t[ORDRE_FEN].drop(index=pivot, errors="ignore").dropna(how="all")
        if t.empty:
            self._tables[pivot] = t
            return t

        t["stabilite"] = (1 - t[ORDRE_FEN].std(axis=1, ddof=0) / ECART_STABILITE).clip(0, 1)
        t.loc[t[ORDRE_FEN].notna().sum(axis=1) < 2, "stabilite"] = np.nan
        t["corr"] = t["90j"].fillna(t["250j"]).fillna(t["30j"])

        socle = t["90j"] - t["250j"]
        derive = t["30j"] - t["250j"]
        transition = (
            (np.sign(socle) == np.sign(derive))
            & (derive.abs() >= DERIVE_TRANSITION)
            & (t["30j"].abs() >= ARRIVEE_MIN)
            & derive.notna()
        )
        t["tendance"] = np.where(
            transition,
            np.where(derive > 0, "TRANSITION ^", "TRANSITION v"),
            np.where(t["stabilite"] < 0.50, "erratique", "-"))

        # Le poids continu. Jamais un seuil.
        t["poids"] = (t["corr"].abs() * t["stabilite"].fillna(0.5)).round(3)

        t["groupe"] = np.where(t["corr"] >= SEUIL_SATELLITE, "satellite",
                      np.where(t["corr"] <= SEUIL_MIROIR, "miroir", "decouple"))

        self._tables[pivot] = t.sort_values("corr", ascending=False)
        self._detecter_ruptures(pivot, t)
        return self._tables[pivot]

    # -- lecture -----------------------------------------------------------
    def membres(self, pivot: str, groupe: str | None = None) -> list[Membre]:
        t = self.table(pivot)
        if t.empty:
            return []
        out = [
            Membre(ticker=tk, corr=float(row["corr"]),
                   corr_30j=float(row["30j"]) if pd.notna(row["30j"]) else float("nan"),
                   corr_90j=float(row["90j"]) if pd.notna(row["90j"]) else float("nan"),
                   corr_250j=float(row["250j"]) if pd.notna(row["250j"]) else float("nan"),
                   stabilite=float(row["stabilite"]) if pd.notna(row["stabilite"]) else 0.5,
                   poids=float(row["poids"]), tendance=str(row["tendance"]),
                   groupe=str(row["groupe"]))
            for tk, row in t.iterrows()
        ]
        if groupe:
            out = [m for m in out if m.groupe == groupe]
        return sorted(out, key=lambda m: m.poids, reverse=True)

    def groupes(self, pivot: str) -> dict[str, list[Membre]]:
        tous = self.membres(pivot)
        return {
            "satellites": [m for m in tous if m.groupe == "satellite"],
            "miroirs": [m for m in tous if m.groupe == "miroir"],
            "decouples": [m for m in tous if m.groupe == "decouple"],
        }

    # -- redondance ---------------------------------------------------------
    def clusters(self, pivot: str) -> list[list[str]]:
        """Regroupe les membres qui portent la MEME information.

        L'argent, les mineurs, le platine et le palladium ne sont pas quatre
        confirmations d'un achat or : c'est le complexe metaux, donc UNE.
        Les huit cryptos n'en font qu'une aussi. Compter 16 votes quand il y
        a 3 informations independantes fabrique une certitude qui n'existe
        pas — c'est la faute qui rend un systeme tres confiant et tres
        perdant.
        """
        cle = f"_cl_{pivot}"
        if hasattr(self, cle):
            return getattr(self, cle)

        membres = [m for m in self.membres(pivot) if m.groupe != "decouple"]
        if not membres:
            setattr(self, cle, [])
            return []

        r = self._rendements(pivot)
        tickers = [m.ticker for m in membres if m.ticker in r.columns]
        mat = r[tickers].tail(250).corr(min_periods=60).abs()

        groupes: list[list[str]] = []
        for m in membres:                      # deja tries par poids decroissant
            if m.ticker not in tickers:
                groupes.append([m.ticker])
                continue
            place = False
            for gr in groupes:
                tete = gr[0]
                if tete in mat.columns and m.ticker in mat.index:
                    c = mat.at[m.ticker, tete]
                    if pd.notna(c) and c >= SEUIL_REDONDANCE:
                        gr.append(m.ticker)
                        place = True
                        break
            if not place:
                groupes.append([m.ticker])
        setattr(self, cle, groupes)
        return groupes

    # -- ruptures de regime ------------------------------------------------
    def _detecter_ruptures(self, pivot: str, t: pd.DataFrame) -> None:
        """Une correlation qui change de SIGNE ou bouge de plus de 0,30
        depuis le dernier calcul est un changement de regime de marche.
        C'est souvent l'information la plus precieuse du systeme : c'est le
        moment ou les strategies calibrees cessent de fonctionner."""
        avant = self._precedent.get(pivot, {})
        for tk, row in t.iterrows():
            c = row["corr"]
            c0 = avant.get(tk)
            if c0 is None or pd.isna(c):
                continue
            if np.sign(c) != np.sign(c0) and min(abs(c), abs(c0)) >= 0.25:
                self._ruptures.append({"pivot": pivot, "actif": tk, "type": "inversion",
                                       "avant": round(c0, 2), "apres": round(c, 2)})
            elif abs(c - c0) >= 0.30:
                self._ruptures.append({"pivot": pivot, "actif": tk, "type": "derive",
                                       "avant": round(c0, 2), "apres": round(c, 2)})

    def ruptures(self) -> list[dict]:
        return self._ruptures

    # -- cache -------------------------------------------------------------
    def _lire_cache(self) -> dict:
        if self.cache and self.cache.exists():
            try:
                return json.loads(self.cache.read_text()).get("corr", {})
            except Exception:
                pass
        return {}

    def sauver(self) -> None:
        if not self.cache:
            return
        corr = {p: {tk: round(float(r["corr"]), 4) for tk, r in t.iterrows()
                    if pd.notna(r["corr"])}
                for p, t in self._tables.items() if not t.empty}
        self.cache.write_text(json.dumps(
            {"quand": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "corr": corr}, ensure_ascii=False, indent=1))


# --------------------------------------------------------------------------
class Miroir:
    """AG-10 — confirmation croisee intermarche.

    biais : {ticker: "haussier" | "baissier" | "neutre"} pour les membres.
    """

    def __init__(self, constellation: Constellation):
        self.c = constellation

    def evaluer(self, pivot: str, sens: str,
                biais: dict[str, str]) -> ScoreIntermarche:
        if sens not in ("achat", "vente"):
            raise ValueError("sens doit etre 'achat' ou 'vente'")
        direction_pivot = 1 if sens == "achat" else -1

        confirment, contredisent, ignores = [], [], []
        somme_ponderee = 0.0
        base = 0.0
        notables: list[str] = []

        par_ticker = {m.ticker: m for m in self.c.membres(pivot)}

        # Un vote par CLUSTER, pas par membre. Le poids du cluster est celui
        # de son membre le plus fort ; son sens est la majorite ponderee
        # interne. Ainsi le complexe metaux vote une fois, pas cinq.
        for groupe in self.c.clusters(pivot):
            num = 0.0      # somme ponderee des accords du cluster
            den = 0.0      # somme des poids ayant vote dans le cluster
            poids_cluster = 0.0

            for tk in groupe:
                m = par_ticker.get(tk)
                if m is None or m.groupe == "decouple":
                    continue
                poids_cluster = max(poids_cluster, m.poids)

                b = biais.get(tk, "neutre")
                # Une correlation erratique ne peut NI confirmer NI contredire.
                if b == "neutre" or m.tendance == "erratique":
                    ignores.append(tk)
                    continue

                direction_membre = 1 if b == "haussier" else -1
                accord = 1 if direction_membre == direction_pivot * m.sens_attendu else -1
                num += m.poids * accord
                den += m.poids
                (confirment if accord > 0 else contredisent).append(tk)

            if den == 0 or poids_cluster == 0:
                continue
            sens_cluster = num / den          # [-1, +1]
            somme_ponderee += poids_cluster * sens_cluster
            base += poids_cluster
            if sens_cluster < 0 and poids_cluster >= POIDS_NOTABLE:
                notables.append(f"{groupe[0]} ({poids_cluster:.2f})")

        score = (somme_ponderee / base) if base > 0 else 0.0
        fiable = base >= BASE_MINIMALE

        # Asymetrie voulue : une base mince peut FAIRE DOUTER mais jamais
        # rassurer. Deux relations faibles qui vont dans le bon sens ne
        # valent pas une confirmation ; une qui va a l'envers reste un
        # avertissement qu'il serait malhonnete d'ignorer.
        brut = 1.0 + AMPLITUDE * score
        facteur = brut if fiable else min(1.0, brut)

        bloque = fiable and score <= SCORE_BLOCAGE
        motif = ""
        if bloque:
            motif = (f"score intermarche {score:+.2f} sous le seuil "
                     f"{SCORE_BLOCAGE:+.2f} — contredisent : "
                     f"{', '.join(contredisent)}")
        elif notables:
            motif = f"contradiction notable (sans blocage) : {', '.join(notables)}"

        return ScoreIntermarche(
            score=round(score, 3), facteur_confiance=round(facteur, 3),
            bloque=bloque, base=round(base, 3), fiable=fiable,
            confirment=confirment, contredisent=contredisent, ignores=ignores,
            motif=motif)

    def appliquer(self, pivot: str, sens: str, confiance: float,
                  biais: dict[str, str]) -> tuple[float, ScoreIntermarche]:
        s = self.evaluer(pivot, sens, biais)
        if s.bloque:
            return 0.0, s
        return round(min(1.0, max(0.0, confiance * s.facteur_confiance)), 3), s


# ==========================================================================
# DEMONSTRATION EXECUTABLE
#
# Le module ci-dessus est une BIBLIOTHEQUE : il sera appele par le systeme.
# Ce bloc sert a le voir tourner en vrai.
#
#     python3 constellation_agent.py             # pivot = or
#     python3 constellation_agent.py BTC-USD     # pivot = bitcoin
# ==========================================================================
NOMS = {
    "GC=F": "Or (XAU/USD)", "SI=F": "Argent (XAG/USD)", "PL=F": "Platine",
    "PA=F": "Palladium", "HG=F": "Cuivre", "CL=F": "Petrole WTI",
    "BZ=F": "Petrole Brent", "NG=F": "Gaz naturel", "DX-Y.NYB": "Dollar Index",
    "^TNX": "Rendement 10 ans US", "^FVX": "Rendement 5 ans US",
    "TIP": "TIPS (taux reels)", "TLT": "Obligations 20 ans+",
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "AUDUSD=X": "AUD/USD",
    "NZDUSD=X": "NZD/USD", "USDCHF=X": "USD/CHF", "USDJPY=X": "USD/JPY",
    "USDCAD=X": "USD/CAD", "EURJPY=X": "EUR/JPY", "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum", "SOL-USD": "Solana", "BNB-USD": "BNB",
    "XRP-USD": "XRP", "ADA-USD": "Cardano", "AVAX-USD": "Avalanche",
    "LINK-USD": "Chainlink", "SPY": "S&P 500", "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000", "GDX": "Mineurs d'or", "^VIX": "VIX (peur)",
    "NVDA": "Nvidia", "AAPL": "Apple", "XLE": "Energie",
}


def biais_provisoire(prix: pd.DataFrame) -> dict[str, str]:
    """Biais haussier/baissier/neutre par actif.

    PROVISOIRE — dans le systeme final, ce biais vient de l'agent AG-02
    Structure (structure de marche, BOS/CHoCH, multi-timeframe). Ici on
    utilise une regle simple pour que la demonstration tourne : position
    du prix par rapport a ses moyennes 20 et 50 jours.
    """
    out = {}
    for c in prix.columns:
        s = prix[c].dropna()
        if len(s) < 60:
            continue
        e20, e50 = s.ewm(span=20).mean().iloc[-1], s.ewm(span=50).mean().iloc[-1]
        # Zone neutre AUTO-CALIBREE sur l'actif lui-meme. Un seuil devine
        # a partir de la volatilite quotidienne se trompe d'un facteur 2 ou 3
        # selon l'actif : sur l'argent il exigeait 3,3 % d'ecart entre les
        # moyennes 20 et 50, un niveau qui ne se produit qu'en tendance
        # extreme. On compare donc l'ecart actuel a SA PROPRE distribution
        # historique, ce qui rend le seuil juste pour chaque actif sans
        # aucune constante devinee.
        ec = (s.ewm(span=20).mean() - s.ewm(span=50).mean()) / s.ewm(span=50).mean()
        sigma = float(ec.tail(250).std())
        if not np.isfinite(sigma) or sigma == 0:
            out[c] = "neutre"
            continue
        z = float(ec.iloc[-1]) / sigma
        out[c] = ("haussier" if z > 0.5 else "baissier" if z < -0.5 else "neutre")
    return out


def _demo(pivot: str, prix: pd.DataFrame) -> None:
    n = lambda t: NOMS.get(t, t)
    ag = Constellation(prix, cache=CACHE)
    g = ag.groupes(pivot)

    print(f"\n{'=' * 78}\n  CONSTELLATION DE {n(pivot).upper()}\n{'=' * 78}")
    for cle, titre in (("satellites", "SATELLITES — memes mouvements"),
                       ("miroirs", "MIROIRS — mouvements opposes")):
        print(f"\n  {titre}")
        if not g[cle]:
            print("    (aucun)")
        for m in g[cle]:
            t = f"  [{m.tendance}]" if m.tendance != "-" else ""
            print(f"    {n(m.ticker):<24} corr {m.corr:+.2f}  "
                  f"poids {m.poids:.2f}{t}")
    print(f"\n  DECOUPLES : {len(g['decouples'])} actifs sans relation exploitable")

    biais = biais_provisoire(prix)
    print(f"\n{'=' * 78}\n  VERDICT INTERMARCHE — biais actuels (moyennes 20/50 j)\n{'=' * 78}")
    for m in g["satellites"] + g["miroirs"]:
        print(f"    {n(m.ticker):<24} {biais.get(m.ticker, 'inconnu')}")

    mi = Miroir(ag)
    print()
    for sens in ("achat", "vente"):
        conf, s = mi.appliquer(pivot, sens, 0.65, biais)
        fleche = "ACHAT " if sens == "achat" else "VENTE "
        print(f"  Hypothese {fleche}{n(pivot)} a 0,65 de confiance")
        print(f"    -> {conf}   {s.resume()}")
        if s.confirment:
            print(f"       confirment  : {', '.join(n(x) for x in s.confirment)}")
        if s.contredisent:
            print(f"       contredisent: {', '.join(n(x) for x in s.contredisent)}")
        print()

    if ag.ruptures():
        print(f"{'=' * 78}\n  RUPTURES DE REGIME depuis le dernier calcul\n{'=' * 78}")
        for r in ag.ruptures():
            print(f"    {n(r['actif']):<24} {r['type']:<10} "
                  f"{r['avant']:+.2f} -> {r['apres']:+.2f}")
    ag.sauver()
    print("  (correlations mises en cache — les ruptures apparaitront au "
          "prochain lancement)\n")


if __name__ == "__main__":
    import sys, warnings
    warnings.filterwarnings("ignore")
    pivot = next((a for a in sys.argv[1:] if not a.startswith("-")), "GC=F")
    if pivot not in NOMS:
        print(f"Pivot inconnu : {pivot}\nDisponibles : {', '.join(NOMS)}")
        sys.exit(1)
    try:
        import yfinance as yf
    except ImportError:
        print("pip3 install yfinance pandas numpy")
        sys.exit(1)
    print(f"Telechargement de {len(NOMS)} actifs (3 ans, quotidien)...")
    d = yf.download(list(NOMS), period="3y", interval="1d",
                    progress=False, auto_adjust=True)["Close"]
    d = d.dropna(axis=1, how="all")
    print(f"OK — {len(d)} lignes, derniere donnee : {d.index[-1].date()}")
    if pivot not in d.columns:
        print(f"Pas de donnees pour {pivot}.")
        sys.exit(1)
    _demo(pivot, d)
