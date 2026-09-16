#!/usr/bin/env python3
"""
PIPS — convertir les signaux résolus en pips gagnés ou perdus.

    python3 pips.py        # démonstration

Remplace le « Profit Factor » de l'historique par le chiffre que tu lis
vraiment : **combien de pips le système a gagnés, ou perdus**.

Le piège qu'il faut connaître avant de lire un total
-----------------------------------------------------
Un pip n'est pas la même chose selon l'instrument :

    1 pip EUR/USD  = 0,0001    → environ 10 $ sur 1 lot
    1 pip USD/JPY  = 0,01      → environ  7 $ sur 1 lot
    1 pip XAU/USD  = 0,01      → environ  1 $ sur 1 lot
    1 point BTC    = 1,00      → 1 $ par unité

Additionner tout ça donne un nombre qui ne correspond à aucune somme
d'argent. **+500 pips sur l'or et −500 pips sur EUR/USD, ce n'est pas
l'équilibre : c'est une grosse perte.**

Ce module affiche donc TOUJOURS le détail par instrument, et le total ne
sert qu'à voir le sens général. Le seul agrégat honnête reste le **R**,
parce qu'un R vaut le même argent partout — c'est sa définition.

Sur les cryptos et les indices, personne ne dit « pip » : le module écrit
« points », il n'invente pas une unité qui n'existe pas.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Taille d'un pip par instrument. C'est une DONNÉE : ajouter un instrument
# ne demande aucune ligne de code.
#   (taille, unité affichée)
# --------------------------------------------------------------------------
TAILLE_PIP: dict[str, tuple[float, str]] = {
    # --- forex majeur ---
    "EURUSD": (0.0001, "pips"), "GBPUSD": (0.0001, "pips"),
    "AUDUSD": (0.0001, "pips"), "NZDUSD": (0.0001, "pips"),
    "USDCHF": (0.0001, "pips"), "USDCAD": (0.0001, "pips"),
    "EURGBP": (0.0001, "pips"), "EURCHF": (0.0001, "pips"),
    # --- paires en yen : le yen a deux décimales de moins ---
    "USDJPY": (0.01, "pips"), "EURJPY": (0.01, "pips"),
    "GBPJPY": (0.01, "pips"), "AUDJPY": (0.01, "pips"),
    # --- métaux ---
    "XAUUSD": (0.01, "pips"),      # l'or : 1,00 $ de mouvement = 100 pips
    "XAGUSD": (0.001, "pips"),     # l'argent
    "CUIVRE": (0.0001, "pips"), "HG=F": (0.0001, "pips"),
    # --- énergie ---
    "WTI": (0.01, "pips"), "BRENT": (0.01, "pips"),
    # --- indices : on dit « points », pas « pips » ---
    "SPX": (1.0, "points"), "US500": (1.0, "points"),
    "NAS100": (1.0, "points"), "DAX": (1.0, "points"),
    # --- crypto : aucune convention de pip n'existe ---
    "BTCUSD": (1.0, "points"), "ETHUSD": (0.1, "points"),
    "SOLUSD": (0.01, "points"), "XRPUSD": (0.0001, "points"),
    # --- ajouts étape 5.3 (16/09) : les instruments réellement présents
    # dans le journal — un inconnu est EXCLU du total, donc chaque ligne
    # ci-dessous rend un morceau du bilan à nouveau comptable. Tailles
    # calées sur la cotation constatée (décimales du registre).
    "XPTUSD": (0.01, "pips"), "XPDUSD": (0.01, "pips"),   # platine, palladium
    "GAZ": (0.001, "pips"), "NG=F": (0.001, "pips"),      # gaz naturel
    "BLE": (0.25, "points"), "MAIS": (0.25, "points"),    # céréales (¢/boisseau)
    "DXY": (0.01, "points"),                              # indice dollar
    "EURAUD": (0.0001, "pips"),
    # actions et ETF américains : 1 point = 1 $ (convention de place)
    "AAPL": (1.0, "points"), "MSFT": (1.0, "points"), "NVDA": (1.0, "points"),
    "GOOGL": (1.0, "points"), "AMZN": (1.0, "points"), "META": (1.0, "points"),
    "TSLA": (1.0, "points"), "AMD": (1.0, "points"), "NFLX": (1.0, "points"),
    "JPM": (1.0, "points"), "XOM": (1.0, "points"),
    "SPY": (1.0, "points"), "QQQ": (1.0, "points"), "IWM": (1.0, "points"),
    "XLE": (1.0, "points"), "XLK": (1.0, "points"), "XLF": (1.0, "points"),
    "GDX": (1.0, "points"),
    # alts : taille = le pas de cotation constaté sur Binance
    "ADAUSD": (0.0001, "points"), "AVAXUSD": (0.01, "points"),
    "LINKUSD": (0.01, "points"), "LTCUSD": (0.01, "points"),
    "ATOMUSD": (0.001, "points"), "NEARUSD": (0.001, "points"),
    "DOTUSD": (0.001, "points"), "BNBUSD": (0.1, "points"),
    "DOGEUSD": (0.00001, "points"), "MATICUSD": (0.0001, "points"),
}

# Repli quand l'instrument n'est pas dans la table.
DEFAUT = (0.0001, "pips")


def normaliser(instrument: str) -> str:
    """EUR/USD, eur-usd, EURUSD= → EURUSD."""
    return "".join(c for c in instrument.upper()
                   if c.isalnum() or c == "=").replace("USDT", "USD")


def taille_pip(instrument: str) -> tuple[float, str]:
    """Taille d'un pip et unité à afficher.

    Hors table, on déduit plutôt que de deviner au hasard :
      · une paire en JPY a deux décimales de moins ;
      · un actif coté au-dessus de 1000 se compte en points, pas en pips —
        annoncer « 4 200 000 pips » sur le Bitcoin serait absurde.

    Le repli est signalé dans le rapport : un instrument mal converti
    fausse son total, et il vaut mieux le voir que le subir.
    """
    n = normaliser(instrument)
    if n in TAILLE_PIP:
        return TAILLE_PIP[n]
    if n.endswith("JPY"):
        return 0.01, "pips"
    return DEFAUT


def est_connu(instrument: str) -> bool:
    n = normaliser(instrument)
    return n in TAILLE_PIP or n.endswith("JPY")


# ==========================================================================
@dataclass
class LignePips:
    instrument: str
    unite: str
    n: int = 0
    gagnes: float = 0.0      # toujours >= 0
    perdus: float = 0.0      # toujours >= 0
    n_tp: int = 0
    n_sl: int = 0
    converti: bool = True    # False = taille de pip devinée

    @property
    def net(self) -> float:
        """Gagnés moins perdus. Négatif quand il y a plus de pertes —
        c'est ce chiffre-là qu'on affiche, signe compris."""
        return self.gagnes - self.perdus

    @property
    def taux(self) -> float:
        return self.n_tp / self.n if self.n else 0.0


@dataclass
class Bilan:
    lignes: list[LignePips] = field(default_factory=list)
    r_total: float = 0.0          # le seul agrégat comparable entre marchés
    n_resolus: int = 0
    n_tp: int = 0

    @property
    def fiables(self) -> list[LignePips]:
        """Les instruments dont la taille de pip est connue.

        Un instrument absent de la table est converti au pif : sur la démo,
        4 signaux « PLATINE » mal convertis produisaient −400 000 et
        représentaient 96 % du total à eux seuls. Les EXCLURE du total et
        les afficher à part est plus honnête que de laisser un chiffre faux
        écraser tous les autres.
        """
        return [l for l in self.lignes if l.converti]

    @property
    def net(self) -> float:
        return sum(l.net for l in self.fiables)

    @property
    def gagnes(self) -> float:
        return sum(l.gagnes for l in self.fiables)

    @property
    def perdus(self) -> float:
        return sum(l.perdus for l in self.fiables)

    @property
    def taux(self) -> float:
        return self.n_tp / self.n_resolus if self.n_resolus else 0.0

    @property
    def melange(self) -> bool:
        """Plusieurs instruments dans le même total : le chiffre global ne
        correspond alors à aucune somme d'argent."""
        return len(self.fiables) > 1


def pips_signal(s) -> float | None:
    """Pips signés d'un signal résolu. TP → positif, SL → négatif.

    Un signal non résolu renvoie None et ne compte nulle part : un trade
    jamais entré n'a fait gagner ni perdre un seul pip.
    """
    statut = getattr(s, "statut", None) or (s.get("statut") if isinstance(s, dict) else None)
    if statut not in ("TP", "SL"):
        return None

    def champ(nom):
        return getattr(s, nom, None) if not isinstance(s, dict) else s.get(nom)

    entree, tp, sl = champ("entree"), champ("tp"), champ("sl")
    if entree is None or tp is None or sl is None:
        return None
    taille, _ = taille_pip(str(champ("instrument") or ""))
    if taille <= 0:
        return None
    distance = abs(tp - entree) if statut == "TP" else -abs(entree - sl)
    return distance / taille


def bilan(signaux) -> Bilan:
    """Le bilan en pips, par instrument puis au total.

    ⚠️ Ne compte QUE les signaux résolus (TP ou SL). Les expirés et les
    « en attente » sont exclus : ils n'ont rien gagné ni perdu, et les
    inclure ferait bouger le total sans qu'aucun trade n'ait eu lieu.
    """
    par_inst: dict[str, LignePips] = {}
    b = Bilan()

    for s in signaux:
        p = pips_signal(s)
        if p is None:
            continue
        inst = str(getattr(s, "instrument", None)
                   or (s.get("instrument") if isinstance(s, dict) else "?"))
        _, unite = taille_pip(inst)
        l = par_inst.get(inst)
        if l is None:
            l = par_inst[inst] = LignePips(inst, unite, converti=est_connu(inst))
        l.n += 1
        if p >= 0:
            l.gagnes += p
            l.n_tp += 1
            b.n_tp += 1
        else:
            l.perdus += -p
            l.n_sl += 1
        b.n_resolus += 1
        r = getattr(s, "r_realise", None)
        if r is not None:
            b.r_total += r

    b.lignes = sorted(par_inst.values(), key=lambda x: -abs(x.net))
    return b


# ==========================================================================
def resume_court(b: Bilan) -> str:
    """La ligne unique qui remplace « Profit Factor » dans l'en-tête.

    Format volontaire : le signe d'abord. « −1 240 pips » se lit en une
    seconde ; « PF 0,42 » demande de se souvenir de ce que vaut un PF.
    """
    if not b.n_resolus:
        return "aucun signal résolu"
    if not b.fiables:
        return (f"{b.n_tp}/{b.n_resolus} TP · {b.r_total:+.1f}R "
                f"· pips non calculables")

    signe = "+" if b.net >= 0 else "−"
    unites = {l.unite for l in b.fiables}
    unite = unites.pop() if len(unites) == 1 else "pips/points"
    txt = f"{signe}{abs(b.net):,.0f} {unite}".replace(",", " ")
    # Le « ≠ » signale que le total mélange des instruments, donc qu'il
    # donne un sens, pas une somme d'argent. Filtre sur UN instrument et
    # il disparaît : le chiffre devient alors exact.
    if b.melange:
        txt += " ≠"
    return f"{txt} · {b.n_tp}/{b.n_resolus} TP · {b.r_total:+.1f}R"


def rapport(b: Bilan) -> str:
    if not b.n_resolus:
        return ("# Pips gagnés / perdus\n\n"
                "Aucun signal résolu. Rien à compter — et c'est une "
                "information, pas une erreur.\n")

    l = ["# Pips gagnés / perdus", "",
         f"**{resume_court(b)}**", "",
         "| instrument | unité | n | TP | gagnés | perdus | **net** | taux |",
         "|---|---|---:|---:|---:|---:|---:|---:|"]
    for x in b.lignes:
        etoile = " ⚠️" if not x.converti else ""
        l.append(f"| {x.instrument}{etoile} | {x.unite} | {x.n} | {x.n_tp} "
                 f"| +{x.gagnes:,.0f} | −{x.perdus:,.0f} "
                 f"| **{'+' if x.net >= 0 else '−'}{abs(x.net):,.0f}** "
                 f"| {x.taux:.0%} |".replace(",", " "))

    n_fiables = sum(x.n for x in b.fiables)
    l += ["", f"Total : **{'+' if b.net >= 0 else '−'}{abs(b.net):,.0f}** "
              f"(+{b.gagnes:,.0f} gagnés, −{b.perdus:,.0f} perdus) "
              f"sur {n_fiables} signaux résolus.".replace(",", " ")]

    if b.melange:
        l += ["", "> ⚠️ **Ce total additionne des unités différentes.** "
                  "1 pip d'EUR/USD ≈ 10 $, 1 pip d'or ≈ 1 $. "
                  "+500 pips sur l'or et −500 sur EUR/USD ne s'annulent pas : "
                  "c'est une perte nette. Le total ci-dessus montre le SENS, "
                  f"pas une somme d'argent. Le chiffre comparable est le "
                  f"**R : {b.r_total:+.1f}R**."]
    absents = [x for x in b.lignes if not x.converti]
    if absents:
        noms = ", ".join(x.instrument for x in absents)
        l += ["", f"> ⚠️ **{noms}** : taille de pip inconnue, donc "
                  f"**exclu(s) du total** ci-dessus. Leur ligne est affichée "
                  f"à titre indicatif et son chiffre est faux. Ajoute-les "
                  f"dans `TAILLE_PIP` de `pips.py` pour les compter."]
    return "\n".join(l) + "\n"


# --------------------------------------------------------------------------
def _demo() -> None:
    @dataclass
    class S:
        instrument: str; entree: float; sl: float; tp: float; statut: str
        @property
        def rr(self):
            r = abs(self.entree - self.sl)
            return abs(self.tp - self.entree) / r if r else 0.0
        @property
        def r_realise(self):
            return self.rr if self.statut == "TP" else -1.0 if self.statut == "SL" else None

    sig = (
        [S("XAUUSD", 2400.0, 2380.0, 2442.0, "TP")] * 12 +
        [S("XAUUSD", 2400.0, 2380.0, 2442.0, "SL")] * 31 +
        [S("EURUSD", 1.0850, 1.0830, 1.0892, "TP")] * 7 +
        [S("EURUSD", 1.0850, 1.0830, 1.0892, "SL")] * 22 +
        [S("BTCUSD", 62000.0, 61000.0, 64100.0, "TP")] * 3 +
        [S("BTCUSD", 62000.0, 61000.0, 64100.0, "SL")] * 9 +
        [S("PLATINE", 980.0, 970.0, 1001.0, "SL")] * 4 +
        [S("XAUUSD", 2400.0, 2380.0, 2442.0, "en_attente")] * 40
    )
    print(rapport(bilan(sig)))
    print("En-tête du site :", resume_court(bilan(sig)))


if __name__ == "__main__":
    _demo()
