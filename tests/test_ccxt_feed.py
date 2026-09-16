"""CHANTIER #10 — l'adaptateur CCXT respecte le contrat feeds/ (sans réseau,
règle 18 : l'exchange est un faux objet injecté)."""
import time

from feeds.ccxt_feed import CcxtFeed, symbole_ccxt
from feeds.base import SeauJetons


class FauxExchange:
    """Sert un historique minute continu, paginé comme un vrai exchange."""

    def __init__(self, total=2500, dur_s=60):
        self.dur_s = dur_s
        fin = int(time.time() // dur_s) * dur_s
        self.t0 = (fin - total * dur_s) * 1000
        self.total = total
        self.appels = 0

    def parse_timeframe(self, iv):
        return self.dur_s

    def milliseconds(self):
        return self.t0 + self.total * self.dur_s * 1000

    def fetch_ohlcv(self, sym, iv, since=None, limit=500):
        self.appels += 1
        assert sym == "BTC/USDT"            # la traduction a bien eu lieu
        pas = self.dur_s * 1000
        debut = self.t0 if since is None else max(self.t0, since)
        i0 = (debut - self.t0) // pas
        out = []
        for i in range(int(i0), min(self.total, int(i0) + limit)):
            t = self.t0 + i * pas
            out.append([t, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 10.0])
        return out


def _feed(ex):
    return CcxtFeed(exchange=ex,
                    seau=SeauJetons(1000, 1000, horloge=lambda: 0.0,
                                    sommeil=lambda s: None),
                    sommeil=lambda s: None)


def test_traduction_symbole():
    assert symbole_ccxt("BTCUSDT") == "BTC/USDT"
    assert symbole_ccxt("DOGEUSDT") == "DOGE/USDT"
    assert symbole_ccxt("ETHBTC") == "ETH/BTC"
    assert symbole_ccxt("BTC/USDT") == "BTC/USDT"


def test_pagination_au_dela_d_une_page(tmp_path, monkeypatch):
    monkeypatch.setattr("feeds.base.DOSSIER_CACHE", tmp_path)
    ex = FauxExchange(total=2500)
    bars = _feed(ex).bars("BTCUSDT", "1", 2000)
    assert len(bars) == 2000
    assert ex.appels >= 2                   # 2000 > MAX_PAR_APPEL : paginé
    assert bars[0]["time"] < bars[-1]["time"]
    # bougies normalisées, format strategy.py
    assert set(bars[0]) == {"time", "open", "high", "low", "close", "volume"}


def test_exchange_muet_ne_boucle_pas(tmp_path, monkeypatch):
    monkeypatch.setattr("feeds.base.DOSSIER_CACHE", tmp_path)

    class Muet(FauxExchange):
        def fetch_ohlcv(self, *a, **k):
            self.appels += 1
            return []
    ex = Muet()
    assert _feed(ex).bars("BTCUSDT", "1", 500) == []
    assert ex.appels == 1


def test_timeframe_inconnu_refuse():
    try:
        _feed(FauxExchange())._fetch("BTCUSDT", "42", 10)
        raise AssertionError("aurait dû lever")
    except ValueError:
        pass
