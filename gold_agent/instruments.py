"""Instruments négociables et leurs caractéristiques de contrat.

Règle 13 : aucune valeur de point écrite en dur dans les calculs — elle
vient toujours de l'objet Instrument. 1 lot XAUUSD = 100 onces, donc un
point de mouvement vaut 100 $ par lot ; ce serait faux sur n'importe quel
autre actif, d'où cet objet.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbole: str          # identifiant canonique (ex : "XAU/USD")
    nom: str
    point_par_lot: float  # valeur d'un point de prix pour 1 lot, en devise de cotation
    decimales: int = 2
    # Cout aller-retour ESTIME (spread + commission + glissement) en % du
    # prix — a affiner par mesure sur le compte reel. Sert au walk-forward :
    # un backtest sans couts est un mensonge (regle 14).
    cout_pct: float = 0.0
    # Identifiants par source de donnees : la traduction de symboles vit
    # ICI, jamais dans un adapter ou un module de calcul (regle 13).
    codes: tuple = ()

    def code_pour(self, source: str) -> str:
        for src, code in self.codes:
            if src == source:
                return code
        return self.symbole


REGISTRE = {
    "XAU/USD": Instrument("XAU/USD", "Or spot", 100.0, 2, cout_pct=0.007,
                          codes=(("yahoo", "GC=F"),)),
    "BTC/USD": Instrument("BTC/USD", "Bitcoin", 1.0, 2, cout_pct=0.05,
                          codes=(("binance", "BTCUSDT"), ("bybit", "BTCUSDT"),
                                 ("yahoo", "BTC-USD"))),
    "ETH/USD": Instrument("ETH/USD", "Ethereum", 1.0, 2, cout_pct=0.07,
                          codes=(("binance", "ETHUSDT"), ("bybit", "ETHUSDT"),
                                 ("yahoo", "ETH-USD"))),
    "EUR/USD": Instrument("EUR/USD", "Euro / dollar", 100000.0, 5, cout_pct=0.010,
                          codes=(("yahoo", "EURUSD=X"),)),
    "SPY": Instrument("SPY", "S&P 500 (ETF)", 1.0, 2, cout_pct=0.020,
                      codes=(("yahoo", "SPY"),)),
}


def par_defaut() -> Instrument:
    """L'or — l'instrument historique du projet ; comportement inchangé."""
    return REGISTRE["XAU/USD"]


def obtenir(symbole: str) -> Instrument:
    return REGISTRE.get(symbole) or par_defaut()


# Noms TradingView / courants -> cle du registre. C'est ici, et seulement
# ici, que la correspondance vit (regle 13 : le symbole comme la valeur du
# point viennent de l'objet Instrument, jamais d'un litteral dans le code).
ALIAS = {"XAUUSD": "XAU/USD", "GOLD": "XAU/USD"}


def depuis_alias(nom: str) -> Instrument | None:
    """Instrument correspondant a un nom TradingView ('OANDA:XAUUSD'), ou None."""
    brut = nom.split(":")[-1].upper()
    cle = ALIAS.get(brut, brut)
    return REGISTRE.get(cle)
