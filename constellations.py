#!/usr/bin/env python3
"""
Calcule les groupes de correlation autour d'un actif pivot.

Usage :
    pip3 install yfinance pandas numpy
    python3 constellations.py             # pivot = or
    python3 constellations.py BTC-USD     # pivot = bitcoin
    python3 constellations.py --liste     # voir tous les pivots possibles

Produit, pour le pivot choisi :
  - SATELLITES : les actifs qui bougent DANS LE MEME SENS
  - MIROIRS    : les actifs qui bougent EN SENS INVERSE
  - DECOUPLES  : ceux qui n'ont pas de relation exploitable
  - un score de STABILITE : la correlation tient-elle dans le temps ?

C'est la brique de base de l'agent AG-09 Constellation.
Aucune cle API n'est necessaire.

------------------------------------------------------------------------------
NOTE DE METHODE — pourquoi le calendrier est le piege principal
------------------------------------------------------------------------------
Le crypto cote 7 jours sur 7, l'or et les actions 5 jours sur 7. Si on
calcule les rendements sur le calendrier fusionne, l'or est absent le
samedi et le dimanche, ET son rendement du lundi est invalide (la veille
n'existe pas). Resultat : ~57 % de valeurs valides, et l'or se fait
eliminer de son propre calcul.

La bonne methode, et c'est celle utilisee ici :
  1. on prend les jours ou LE PIVOT a reellement cote
  2. on reporte la derniere valeur connue des autres actifs sur ces jours
  3. on calcule les rendements sur ce calendrier-la uniquement
Le mouvement d'un crypto pendant le week-end est ainsi absorbe dans le
rendement du lundi, ce qui est le traitement correct pour comparer un
actif 7j/7 a un actif 5j/7.
"""
from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------
# Univers. Ajoute ce que tu veux : le calcul est agnostique.
# --------------------------------------------------------------------------
UNIVERS = {
    # Metaux et matieres premieres
    "GC=F": "Or (XAU/USD)",
    "SI=F": "Argent (XAG/USD)",
    "PL=F": "Platine",
    "PA=F": "Palladium",
    "HG=F": "Cuivre",
    "CL=F": "Petrole WTI",
    "BZ=F": "Petrole Brent",
    "NG=F": "Gaz naturel",
    # Dollar et taux — les moteurs fondamentaux de l'or
    "DX-Y.NYB": "Dollar Index (DXY)",
    "^TNX": "Rendement 10 ans US",
    "^FVX": "Rendement 5 ans US",
    "TIP": "TIPS (taux reels)",
    "TLT": "Obligations 20 ans+",
    # Forex
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "AUDUSD=X": "AUD/USD",
    "NZDUSD=X": "NZD/USD",
    "USDCHF=X": "USD/CHF",
    "USDJPY=X": "USD/JPY",
    "USDCAD=X": "USD/CAD",
    "EURJPY=X": "EUR/JPY",
    # Crypto
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
    "BNB-USD": "BNB",
    "XRP-USD": "XRP",
    "ADA-USD": "Cardano",
    "AVAX-USD": "Avalanche",
    "LINK-USD": "Chainlink",
    # Actions et risque
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000",
    "GDX": "Mineurs d'or",
    "^VIX": "VIX (peur)",
    "NVDA": "Nvidia",
    "AAPL": "Apple",
    "XLE": "Energie",
}

FENETRES = {"30j": 30, "90j": 90, "250j": 250}
ORDRE_FEN = list(FENETRES)

SEUIL_SATELLITE = 0.40     # corr >= +0,40  -> meme sens
SEUIL_MIROIR = -0.40       # corr <= -0,40  -> sens inverse
COUVERTURE_MIN = 0.60      # % de rendements valides exiges sur la fenetre
ECART_STABILITE = 0.35     # normalisation du score de stabilite

# Deux seuils differents, et c'est important :
#   - REGROUPEMENT : a partir de quand on affiche un actif dans le groupe
#   - CONFIRMATION : a partir de quand on a le droit de s'en servir comme
#     confirmation dans une decision. Une correlation de 0,45 n'explique que
#     20 % de la variance : elle informe, elle ne confirme pas.
SEUIL_CONFIRMATION = 0.70
DERIVE_TRANSITION = 0.25   # ecart 30j-250j au-dela duquel on parle de transition
ARRIVEE_MIN = 0.30         # correlation actuelle minimale pour qualifier une transition


# --------------------------------------------------------------------------
# Donnees
# --------------------------------------------------------------------------
def charger(tickers: list[str], periode: str = "3y") -> pd.DataFrame:
    d = yf.download(tickers, period=periode, interval="1d",
                    progress=False, auto_adjust=True)["Close"]
    if isinstance(d, pd.Series):
        d = d.to_frame()
    return d.dropna(axis=1, how="all")


def rendements_sur_calendrier_pivot(prix: pd.DataFrame, pivot: str) -> pd.DataFrame:
    """Log-rendements alignes sur les jours de cotation du PIVOT.

    On correle les RENDEMENTS, jamais les prix : deux series qui montent
    toutes les deux sur 3 ans donnent une correlation de prix elevee qui
    ne dit rien d'exploitable.
    """
    if pivot not in prix.columns:
        raise KeyError(pivot)

    # Jours ou le pivot a reellement cote (avant tout report de valeur).
    jours = prix[pivot].dropna().index
    if len(jours) < 60:
        raise ValueError(f"pivot {pivot} : seulement {len(jours)} jours de cotation")

    # Report de la derniere valeur connue, puis restriction a ces jours.
    aligne = prix.ffill().loc[jours]

    r = np.log(aligne / aligne.shift(1))
    return r.replace([np.inf, -np.inf], np.nan).iloc[1:]


# --------------------------------------------------------------------------
# Correlations
# --------------------------------------------------------------------------
def table_correlations(r: pd.DataFrame, pivot: str) -> tuple[pd.DataFrame, list[str]]:
    """Retourne (table, ecartes) — ecartes = colonnes trop lacunaires."""
    colonnes = {}
    ecartes: set[str] = set()

    for nom, n in FENETRES.items():
        x = r.tail(n)
        garde = x.columns[x.notna().sum() >= n * COUVERTURE_MIN]
        ecartes |= set(x.columns) - set(garde)
        x = x[garde]

        if pivot not in x.columns or x.shape[1] < 2:
            continue
        colonnes[nom] = x.corr(min_periods=int(n * 0.5))[pivot]

    if not colonnes:
        return pd.DataFrame(), sorted(ecartes)

    t = pd.DataFrame(colonnes)
    # Garantit les 3 colonnes meme si une fenetre a echoue.
    for nom in ORDRE_FEN:
        if nom not in t.columns:
            t[nom] = np.nan
    t = t[ORDRE_FEN]

    if pivot in t.index:
        t = t.drop(index=pivot)
    t = t.dropna(how="all")
    if t.empty:
        return t, sorted(ecartes)

    # Stabilite : 1 = la correlation ne bouge pas d'une fenetre a l'autre,
    # 0 = elle tourne completement. Une correlation forte mais instable
    # n'est PAS exploitable — c'est le piege classique.
    ecart = t[ORDRE_FEN].std(axis=1, ddof=0)
    t["stabilite"] = (1 - (ecart / ECART_STABILITE)).clip(0, 1)
    # Une seule fenetre disponible : on ne peut rien dire de la stabilite.
    t.loc[t[ORDRE_FEN].notna().sum(axis=1) < 2, "stabilite"] = np.nan

    # Correlation de reference : 90 jours, repli sur 250 puis 30.
    t["corr"] = t["90j"].fillna(t["250j"]).fillna(t["30j"])

    # TENDANCE — une correlation qui derive dans une direction n'est pas
    # erratique : elle change de regime. C'est souvent l'information la plus
    # precieuse du tableau. Une correlation qui zigzague sans direction est
    # erratique et ne vaut rien.
    #
    # On s'appuie sur l'ecart 90j-250j (echantillons larges, donc fiable) et
    # on demande seulement que le 30j aille DANS LE MEME SENS — sans exiger
    # une monotonie stricte : sur 30 points, un repli de 0,05 est du bruit et
    # ne doit pas annuler une derive de +0,30.
    socle = t["90j"] - t["250j"]          # derive de fond
    derive = t["30j"] - t["250j"]         # derive totale
    coherent = np.sign(socle) == np.sign(derive)
    assez = derive.abs() >= DERIVE_TRANSITION
    # Le point d'ARRIVEE doit compter. Passer de -0,15 a +0,15 coche la
    # case "derive coherente" mais decrit un actif qui n'a jamais eu de
    # relation avec le pivot : ce n'est pas un changement de regime, c'est
    # du bruit qui traverse zero.
    arrivee = t["30j"].abs() >= ARRIVEE_MIN
    t["derive"] = derive
    t["tendance"] = np.where(
        coherent & assez & arrivee & derive.notna(),
        np.where(derive > 0, "TRANSITION ^", "TRANSITION v"),
        np.where(t["stabilite"] < 0.50, "erratique", "-"))

    # POIDS DE CONFIRMATION — continu, jamais un seuil.
    # C'est CETTE valeur que l'agent AG-10 Miroir doit utiliser. Les
    # etiquettes ci-dessous sont pour l'oeil humain ; une decision ne se
    # prend jamais sur un seuil binaire applique a une grandeur continue,
    # sinon 0,49 et 0,51 donnent deux comportements opposes.
    t["poids"] = (t["corr"].abs() * t["stabilite"].fillna(0.5)).round(2)

    fort = (t["corr"].abs() >= SEUIL_CONFIRMATION) & (t["stabilite"] >= 0.75)
    moyen = (t["corr"].abs() >= 0.50) & (t["stabilite"] >= 0.50)
    t["confirmation"] = np.where(fort, "FORTE", np.where(moyen, "moyenne", "aucune"))

    return t.sort_values("corr", ascending=False), sorted(ecartes)


def classer(t: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "SATELLITES": t[t["corr"] >= SEUIL_SATELLITE],
        "DECOUPLES": t[(t["corr"] > SEUIL_MIROIR) & (t["corr"] < SEUIL_SATELLITE)],
        "MIROIRS": t[t["corr"] <= SEUIL_MIROIR].sort_values("corr"),
    }


# --------------------------------------------------------------------------
# Affichage
# --------------------------------------------------------------------------
def libelle_stabilite(s, tendance: str = "-") -> str:
    # Une correlation en transition n'est pas "instable" : elle est
    # directionnelle. Afficher INSTABLE a cote de TRANSITION ^ serait
    # contradictoire pour le lecteur.
    if isinstance(tendance, str) and tendance.startswith("TRANSITION"):
        return "transition"
    if pd.isna(s):
        return "?"
    if s >= 0.75:
        return "stable"
    if s >= 0.50:
        return "moyenne"
    return "INSTABLE"


def _f(v) -> str:
    return f"{v:+.2f}" if pd.notna(v) else "   ."


def afficher(groupes: dict[str, pd.DataFrame], pivot: str) -> None:
    titres = {
        "SATELLITES": ("SATELLITES", "montent quand le pivot monte"),
        "MIROIRS": ("MIROIRS", "baissent quand le pivot monte"),
        "DECOUPLES": ("DECOUPLES", "pas de relation exploitable"),
    }
    nom_pivot = UNIVERS.get(pivot, pivot).upper()

    for cle in ("SATELLITES", "MIROIRS", "DECOUPLES"):
        g = groupes[cle]
        titre, explication = titres[cle]
        print(f"\n{'=' * 78}")
        print(f"  {titre} DE {nom_pivot}  —  {explication}")
        print(f"{'=' * 78}")
        if g.empty:
            print("  (aucun)")
            continue
        print(f"  {'Actif':<24} {'30j':>7} {'90j':>7} {'250j':>7}  "
              f"{'stabilite':<11} {'tendance':<13} {'poids':>5}  confirmation")
        print(f"  {'-' * 92}")
        for tk, row in g.iterrows():
            print(f"  {UNIVERS.get(tk, tk):<24} "
                  f"{_f(row['30j']):>7} {_f(row['90j']):>7} {_f(row['250j']):>7}  "
                  f"{libelle_stabilite(row['stabilite'], row['tendance']):<11} "
                  f"{row['tendance']:<13} {row['poids']:>5.2f}  {row['confirmation']}")


LECTURE = """
  · On correle les RENDEMENTS quotidiens, pas les prix.
  · Le calendrier est aligne sur les jours de cotation du pivot : le
    mouvement d'un crypto pendant le week-end est absorbe dans le lundi.
  · Une correlation marquee INSTABLE ne doit PAS servir de confirmation :
    elle a tourne entre les fenetres 30j / 90j / 250j.
  · Ces valeurs ne sont JAMAIS a ecrire en dur dans le systeme.
    L'agent AG-09 les recalcule toutes les 6 h — les regimes de correlation
    changent, parfois en quelques semaines.
  · Usage dans le systeme :
      un signal ACHAT sur le pivot est CONFIRME  si les satellites sont
      haussiers ET les miroirs baissiers ;
      il est CONTREDIT si un miroir STABLE monte en meme temps que le pivot.
  · Une divergence entre le pivot et un satellite habituellement stable
    (l'or monte, l'argent ne suit pas) est une piste de rattrapage.
"""


# --------------------------------------------------------------------------
def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--liste" in sys.argv:
        for tk, nom in UNIVERS.items():
            print(f"  {tk:<12} {nom}")
        return

    pivot = args[0] if args else "GC=F"
    if pivot not in UNIVERS:
        print(f"Pivot inconnu : {pivot}")
        print("Lance  python3 constellations.py --liste  pour voir les pivots.")
        sys.exit(1)

    print(f"Telechargement de {len(UNIVERS)} actifs (3 ans, quotidien)...")
    prix = charger(list(UNIVERS))
    manquants = [t for t in UNIVERS if t not in prix.columns]
    print(f"OK — {len(prix)} lignes, derniere donnee : {prix.index[-1].date()}")
    if manquants:
        print(f"Non telecharges ({len(manquants)}) : "
              f"{', '.join(UNIVERS[t] for t in manquants)}")

    try:
        r = rendements_sur_calendrier_pivot(prix, pivot)
    except (KeyError, ValueError) as e:
        print(f"\nImpossible d'utiliser {pivot} comme pivot : {e}")
        sys.exit(1)

    print(f"Calendrier du pivot : {len(r)} jours de cotation "
          f"({r.index[0].date()} -> {r.index[-1].date()})")

    t, ecartes = table_correlations(r, pivot)
    if t.empty:
        print("\nAucune correlation exploitable — donnees insuffisantes.")
        sys.exit(1)

    afficher(classer(t), pivot)

    if ecartes:
        noms = [UNIVERS.get(x, x) for x in ecartes if x != pivot]
        if noms:
            print(f"\n  Ecartes pour donnees insuffisantes : {', '.join(noms)}")

    print(f"\n{'=' * 78}")
    print("  LECTURE")
    print(f"{'=' * 78}")
    print(LECTURE)


if __name__ == "__main__":
    main()
