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
    symbole: str          # identifiant Twelve Data (ex : "XAU/USD")
    nom: str
    point_par_lot: float  # valeur d'un point de prix pour 1 lot, en devise de cotation
    decimales: int = 2


REGISTRE = {
    "XAU/USD": Instrument("XAU/USD", "Or spot", 100.0, 2),
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
