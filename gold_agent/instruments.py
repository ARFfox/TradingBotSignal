"""Instruments négociables — LE registre unique du système (SPEC_SITE_V3 §1).

Règle 13 : la valeur du point, le tick, les décimales et la traduction de
symboles vivent ICI, jamais dans une constante ou une table locale d'un
module de calcul. Ajouter un instrument = ajouter une ligne, aucun code.

Chaque instrument porte ses identifiants par source :
  tv       — symbole TradingView PRÉFIXÉ PAR LA PLACE ("OANDA:XAUUSD") ;
             sans lui, le widget resterait bloqué sur l'or quoi qu'on clique
  yahoo    — yfinance ("GC=F"), l'historique différé de la grille
  binance  — spot crypto ("BTCUSDT"), temps réel gratuit
  twelvedata — le flux temps réel payant (l'or seulement, quota 800/j/clé)

⚠️ point_par_lot = 0.0 signifie « valeur du point NON VÉRIFIÉE sur le
compte réel » : risk/notify REFUSENT alors tout calcul de taille plutôt
que d'afficher un volume faux d'un facteur 100 (le bug qui vide un compte).
Seuls les instruments vérifiés portent une valeur.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbole: str          # identifiant canonique AFFICHÉ (ex : "XAU/USD")
    nom: str
    point_par_lot: float  # 0.0 = non vérifié -> sizing refusé
    decimales: int = 2
    # Cout aller-retour ESTIMÉ (spread + commission + glissement) en % du
    # prix — à affiner par mesure sur le compte réel (règle 14).
    cout_pct: float = 0.05
    # Identifiants par source de données — la traduction vit ICI.
    codes: tuple = ()
    marche: str = "matieres"   # matieres | forex | crypto | actions
    tick: float = 0.01

    @property
    def cle(self) -> str:
        """Identifiant interne pour les URL (#/matieres/XAUUSD)."""
        return (self.symbole.replace("/", "").replace("=", "")
                .replace("^", "").replace("-", ""))

    def code_pour(self, source: str) -> str:
        for src, code in self.codes:
            if src == source:
                return code
        return self.symbole


def _i(symbole, nom, marche, tv, yahoo=None, binance=None, td=None,
       point=0.0, dec=2, tick=0.01, cout=0.05):
    codes = [("tv", tv)]
    if yahoo:
        codes.append(("yahoo", yahoo))
    if binance:
        codes.append(("binance", binance))
        codes.append(("bybit", binance))
    if td:
        codes.append(("twelvedata", td))
    return Instrument(symbole, nom, point, dec, cout_pct=cout,
                      codes=tuple(codes), marche=marche, tick=tick)


REGISTRE = {i.symbole: i for i in [
    # ---- MATIÈRES (10) — l'or est le seul instrument VÉRIFIÉ du compte
    _i("XAU/USD", "Or spot", "matieres", "OANDA:XAUUSD", "GC=F",
       td="XAU/USD", point=100.0, dec=2, cout=0.007),
    _i("XAG/USD", "Argent spot", "matieres", "OANDA:XAGUSD", "SI=F",
       dec=3, tick=0.001, cout=0.03),
    _i("XPT/USD", "Platine", "matieres", "OANDA:XPTUSD", "PL=F", cout=0.05),
    _i("XPD/USD", "Palladium", "matieres", "OANDA:XPDUSD", "PA=F", cout=0.08),
    _i("CUIVRE", "Cuivre", "matieres", "COMEX:HG1!", "HG=F",
       dec=4, tick=0.0005, cout=0.05),
    _i("WTI", "Pétrole WTI", "matieres", "TVC:USOIL", "CL=F", cout=0.04),
    _i("BRENT", "Pétrole Brent", "matieres", "TVC:UKOIL", "BZ=F", cout=0.04),
    _i("GAZ", "Gaz naturel", "matieres", "NYMEX:NG1!", "NG=F",
       dec=3, tick=0.001, cout=0.10),
    _i("BLE", "Blé", "matieres", "CBOT:ZW1!", "ZW=F", cout=0.06),
    _i("MAIS", "Maïs", "matieres", "CBOT:ZC1!", "ZC=F", cout=0.06),
    # ---- FOREX (14)
    _i("EUR/USD", "Euro / dollar", "forex", "OANDA:EURUSD", "EURUSD=X",
       point=100000.0, dec=5, tick=0.00001, cout=0.010),
    _i("GBP/USD", "Livre / dollar", "forex", "OANDA:GBPUSD", "GBPUSD=X",
       dec=5, tick=0.00001, cout=0.012),
    _i("USD/JPY", "Dollar / yen", "forex", "OANDA:USDJPY", "USDJPY=X",
       dec=3, tick=0.001, cout=0.010),
    _i("USD/CHF", "Dollar / franc", "forex", "OANDA:USDCHF", "USDCHF=X",
       dec=5, tick=0.00001, cout=0.013),
    _i("AUD/USD", "Aussie / dollar", "forex", "OANDA:AUDUSD", "AUDUSD=X",
       dec=5, tick=0.00001, cout=0.012),
    _i("NZD/USD", "Kiwi / dollar", "forex", "OANDA:NZDUSD", "NZDUSD=X",
       dec=5, tick=0.00001, cout=0.015),
    _i("USD/CAD", "Dollar / loonie", "forex", "OANDA:USDCAD", "USDCAD=X",
       dec=5, tick=0.00001, cout=0.013),
    _i("EUR/JPY", "Euro / yen", "forex", "OANDA:EURJPY", "EURJPY=X",
       dec=3, tick=0.001, cout=0.013),
    _i("GBP/JPY", "Livre / yen", "forex", "OANDA:GBPJPY", "GBPJPY=X",
       dec=3, tick=0.001, cout=0.018),
    _i("EUR/GBP", "Euro / livre", "forex", "OANDA:EURGBP", "EURGBP=X",
       dec=5, tick=0.00001, cout=0.013),
    _i("EUR/AUD", "Euro / aussie", "forex", "OANDA:EURAUD", "EURAUD=X",
       dec=5, tick=0.00001, cout=0.018),
    _i("AUD/JPY", "Aussie / yen", "forex", "OANDA:AUDJPY", "AUDJPY=X",
       dec=3, tick=0.001, cout=0.015),
    _i("CHF/JPY", "Franc / yen", "forex", "OANDA:CHFJPY", "CHFJPY=X",
       dec=3, tick=0.001, cout=0.018),
    _i("DXY", "Dollar Index", "forex", "TVC:DXY", "DX-Y.NYB",
       dec=3, tick=0.001, cout=0.02),
    # ---- CRYPTO (14)
    _i("BTC/USD", "Bitcoin", "crypto", "BINANCE:BTCUSDT", "BTC-USD",
       "BTCUSDT", point=1.0, cout=0.05),
    _i("ETH/USD", "Ethereum", "crypto", "BINANCE:ETHUSDT", "ETH-USD",
       "ETHUSDT", point=1.0, cout=0.07),
    _i("SOL/USD", "Solana", "crypto", "BINANCE:SOLUSDT", "SOL-USD",
       "SOLUSDT", dec=3, tick=0.001, cout=0.08),
    _i("BNB/USD", "BNB", "crypto", "BINANCE:BNBUSDT", "BNB-USD",
       "BNBUSDT", cout=0.08),
    _i("XRP/USD", "XRP", "crypto", "BINANCE:XRPUSDT", "XRP-USD",
       "XRPUSDT", dec=4, tick=0.0001, cout=0.08),
    _i("ADA/USD", "Cardano", "crypto", "BINANCE:ADAUSDT", "ADA-USD",
       "ADAUSDT", dec=4, tick=0.0001, cout=0.09),
    _i("AVAX/USD", "Avalanche", "crypto", "BINANCE:AVAXUSDT", "AVAX-USD",
       "AVAXUSDT", dec=3, tick=0.001, cout=0.09),
    _i("LINK/USD", "Chainlink", "crypto", "BINANCE:LINKUSDT", "LINK-USD",
       "LINKUSDT", dec=3, tick=0.001, cout=0.09),
    _i("DOT/USD", "Polkadot", "crypto", "BINANCE:DOTUSDT", "DOT-USD",
       "DOTUSDT", dec=3, tick=0.001, cout=0.09),
    # MATIC : renomme POL chez Binance — code binance volontairement absent,
    # le repli yfinance fait foi plutot qu'un symbole peut-etre mort.
    _i("MATIC/USD", "Polygon", "crypto", "BINANCE:POLUSDT", "MATIC-USD",
       dec=4, tick=0.0001, cout=0.10),
    _i("DOGE/USD", "Dogecoin", "crypto", "BINANCE:DOGEUSDT", "DOGE-USD",
       "DOGEUSDT", dec=5, tick=0.00001, cout=0.10),
    _i("LTC/USD", "Litecoin", "crypto", "BINANCE:LTCUSDT", "LTC-USD",
       "LTCUSDT", cout=0.08),
    _i("ATOM/USD", "Cosmos", "crypto", "BINANCE:ATOMUSDT", "ATOM-USD",
       "ATOMUSDT", dec=3, tick=0.001, cout=0.10),
    _i("NEAR/USD", "NEAR", "crypto", "BINANCE:NEARUSDT", "NEAR-USD",
       "NEARUSDT", dec=3, tick=0.001, cout=0.10),
    # ---- ACTIONS / ETF (18)
    _i("SPY", "S&P 500 (ETF)", "actions", "AMEX:SPY", "SPY",
       point=1.0, cout=0.020),
    _i("QQQ", "Nasdaq 100 (ETF)", "actions", "NASDAQ:QQQ", "QQQ", cout=0.02),
    _i("IWM", "Russell 2000 (ETF)", "actions", "AMEX:IWM", "IWM", cout=0.03),
    _i("AAPL", "Apple", "actions", "NASDAQ:AAPL", "AAPL", cout=0.02),
    _i("MSFT", "Microsoft", "actions", "NASDAQ:MSFT", "MSFT", cout=0.02),
    _i("NVDA", "Nvidia", "actions", "NASDAQ:NVDA", "NVDA", cout=0.02),
    _i("GOOGL", "Alphabet", "actions", "NASDAQ:GOOGL", "GOOGL", cout=0.02),
    _i("AMZN", "Amazon", "actions", "NASDAQ:AMZN", "AMZN", cout=0.02),
    _i("META", "Meta", "actions", "NASDAQ:META", "META", cout=0.02),
    _i("TSLA", "Tesla", "actions", "NASDAQ:TSLA", "TSLA", cout=0.03),
    _i("AMD", "AMD", "actions", "NASDAQ:AMD", "AMD", cout=0.03),
    _i("NFLX", "Netflix", "actions", "NASDAQ:NFLX", "NFLX", cout=0.03),
    _i("JPM", "JPMorgan", "actions", "NYSE:JPM", "JPM", cout=0.02),
    _i("XOM", "ExxonMobil", "actions", "NYSE:XOM", "XOM", cout=0.02),
    _i("XLE", "Énergie (ETF)", "actions", "AMEX:XLE", "XLE", cout=0.03),
    _i("XLF", "Finance (ETF)", "actions", "AMEX:XLF", "XLF", cout=0.03),
    _i("XLK", "Tech (ETF)", "actions", "AMEX:XLK", "XLK", cout=0.03),
    _i("GDX", "Mineurs d'or (ETF)", "actions", "AMEX:GDX", "GDX", cout=0.03),
]}

MARCHES_ORDRE = ["matieres", "forex", "crypto", "actions"]
MARCHES_LIBELLES = {"matieres": ("🥇", "MATIÈRES"), "forex": ("💱", "FOREX"),
                    "crypto": ("🪙", "CRYPTO"), "actions": ("📈", "ACTIONS")}


def par_defaut() -> Instrument:
    """L'or — l'instrument historique du projet ; comportement inchangé."""
    return REGISTRE["XAU/USD"]


def obtenir(symbole: str) -> Instrument:
    return REGISTRE.get(symbole) or par_defaut()


def par_cle(cle: str) -> Instrument | None:
    """Depuis l'identifiant d'URL ("XAUUSD") vers l'Instrument."""
    for inst in REGISTRE.values():
        if inst.cle == cle:
            return inst
    return None


def par_marche(marche: str) -> list[Instrument]:
    return [i for i in REGISTRE.values() if i.marche == marche]


# Noms TradingView / courants -> cle du registre. C'est ici, et seulement
# ici, que la correspondance vit (regle 13).
ALIAS = {"XAUUSD": "XAU/USD", "GOLD": "XAU/USD"}


def depuis_alias(nom: str) -> Instrument | None:
    """Instrument correspondant a un nom TradingView ('OANDA:XAUUSD'), ou None."""
    brut = nom.split(":")[-1].upper()
    cle = ALIAS.get(brut, brut)
    if cle in REGISTRE:
        return REGISTRE[cle]
    return par_cle(brut)
