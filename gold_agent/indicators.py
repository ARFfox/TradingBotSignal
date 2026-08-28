"""Indicateurs techniques en Python pur — aucune dépendance externe.

Conventions : chaque fonction renvoie une liste de la même longueur que
l'entrée, avec None pour les périodes de préchauffe. Les moyennes de Wilder
(RSI, ATR, ADX) suivent la définition d'origine, qui est celle utilisée par
TradingView.
"""
from __future__ import annotations

from typing import Optional, Sequence

Num = Optional[float]


def sma(values: Sequence[float], length: int) -> list[Num]:
    out: list[Num] = [None] * len(values)
    if length <= 0 or len(values) < length:
        return out
    running = sum(values[:length])
    out[length - 1] = running / length
    for i in range(length, len(values)):
        running += values[i] - values[i - length]
        out[i] = running / length
    return out


def ema(values: Sequence[float], length: int) -> list[Num]:
    out: list[Num] = [None] * len(values)
    if length <= 0 or len(values) < length:
        return out
    k = 2.0 / (length + 1)
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    prev = seed
    for i in range(length, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rma(values: Sequence[Num], length: int) -> list[Num]:
    """Moyenne de Wilder (RMA), base du RSI et de l'ATR chez TradingView."""
    out: list[Num] = [None] * len(values)
    clean = [v for v in values if v is not None]
    if length <= 0 or len(clean) < length:
        return out
    start = next(i for i, v in enumerate(values) if v is not None)
    first_window = values[start:start + length]
    if len(first_window) < length:
        return out
    prev = sum(first_window) / length
    out[start + length - 1] = prev
    for i in range(start + length, len(values)):
        v = values[i]
        if v is None:
            out[i] = prev
            continue
        prev = (prev * (length - 1) + v) / length
        out[i] = prev
    return out


def rsi(closes: Sequence[float], length: int = 14) -> list[Num]:
    n = len(closes)
    out: list[Num] = [None] * n
    if n < length + 1:
        return out
    gains: list[Num] = [None]
    losses: list[Num] = [None]
    for i in range(1, n):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = rma(gains, length)
    avg_loss = rma(losses, length)
    for i in range(n):
        g, l = avg_gain[i], avg_loss[i]
        if g is None or l is None:
            continue
        if l == 0:
            out[i] = 100.0
        else:
            rs = g / l
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def true_range(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> list[Num]:
    out: list[Num] = [None]
    for i in range(1, len(closes)):
        out.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    return out


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], length: int = 14) -> list[Num]:
    return rma(true_range(highs, lows, closes), length)


def macd(closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9):
    ef, es = ema(closes, fast), ema(closes, slow)
    line: list[Num] = [
        (a - b) if (a is not None and b is not None) else None for a, b in zip(ef, es)
    ]
    valid = [v for v in line if v is not None]
    sig: list[Num] = [None] * len(line)
    if len(valid) >= signal:
        offset = len(line) - len(valid)
        sig_vals = ema(valid, signal)
        for i, v in enumerate(sig_vals):
            sig[offset + i] = v
    hist: list[Num] = [
        (m - s) if (m is not None and s is not None) else None for m, s in zip(line, sig)
    ]
    return {"macd": line, "signal": sig, "histogram": hist}


def bollinger(closes: Sequence[float], length: int = 20, mult: float = 2.0):
    basis = sma(closes, length)
    upper: list[Num] = [None] * len(closes)
    lower: list[Num] = [None] * len(closes)
    for i in range(length - 1, len(closes)):
        window = closes[i - length + 1:i + 1]
        mean = basis[i]
        var = sum((x - mean) ** 2 for x in window) / length
        sd = var ** 0.5
        upper[i] = mean + mult * sd
        lower[i] = mean - mult * sd
    return {"basis": basis, "upper": upper, "lower": lower}


def adx(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], length: int = 14):
    """ADX de Wilder — mesure la FORCE de la tendance, pas sa direction."""
    n = len(closes)
    plus_dm: list[Num] = [None]
    minus_dm: list[Num] = [None]
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
    tr_s = rma(true_range(highs, lows, closes), length)
    plus_s = rma(plus_dm, length)
    minus_s = rma(minus_dm, length)
    plus_di: list[Num] = [None] * n
    minus_di: list[Num] = [None] * n
    dx: list[Num] = [None] * n
    for i in range(n):
        if tr_s[i] in (None, 0) or plus_s[i] is None or minus_s[i] is None:
            continue
        pdi = 100.0 * plus_s[i] / tr_s[i]
        mdi = 100.0 * minus_s[i] / tr_s[i]
        plus_di[i], minus_di[i] = pdi, mdi
        denom = pdi + mdi
        dx[i] = 0.0 if denom == 0 else 100.0 * abs(pdi - mdi) / denom
    return {"adx": rma(dx, length), "plus_di": plus_di, "minus_di": minus_di}


def last_valid(series: Sequence[Num]) -> Num:
    for v in reversed(series):
        if v is not None:
            return v
    return None
