import hashlib
import json

import numpy as np
from scipy import stats

from app.ml_features import contiguous_span, rolling_mean

DEFAULT_MARGIN = 0.0235
DEFAULT_TARGET = 6000
MAX_SEQ = 12
EPS = 1e-9
SPEC_KEYS = {"symbols", "trigger", "contract", "duration", "margin", "target_trades", "window"}
FREQ_CONDITIONS = ("freq_below", "freq_at_least", "top_in", "pointer_is_least_of")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def clean_digits(value, minimum=1):
    if not isinstance(value, list) or len(value) < minimum or not all(is_int(v) and 0 <= v <= 9 for v in value):
        raise ValueError("digits must be a list of digits 0 to 9")
    return sorted(set(value))


def clean_pct(value):
    if not is_number(value) or not 0 < value < 100:
        raise ValueError("pct must be a number between 0 and 100")
    return float(value)


def clean_condition(cond):
    if not isinstance(cond, dict) or len(cond) != 1:
        raise ValueError("each trigger condition must be an object with exactly one key")
    key, value = next(iter(cond.items()))
    if key == "parity":
        if value not in ("even", "odd"):
            raise ValueError("parity must be 'even' or 'odd'")
        return {"parity": value}
    if key == "digit_in":
        return {"digit_in": clean_digits(value)}
    if key == "move":
        if value not in ("up", "down", "flat"):
            raise ValueError("move must be 'up', 'down' or 'flat'")
        return {"move": value}
    if key == "any":
        return {"any": True}
    if key == "freq_below":
        if not isinstance(value, dict) or set(value) != {"digits", "pct"}:
            raise ValueError("freq_below needs exactly digits and pct")
        return {"freq_below": {"digits": clean_digits(value["digits"]), "pct": clean_pct(value["pct"])}}
    if key == "freq_at_least":
        if not isinstance(value, dict) or set(value) != {"digits", "pct", "count"}:
            raise ValueError("freq_at_least needs exactly digits, pct and count")
        digits = clean_digits(value["digits"])
        count = value["count"]
        if not is_int(count) or not 1 <= count <= len(digits):
            raise ValueError("count must be a whole number from 1 to the number of digits")
        return {"freq_at_least": {"digits": digits, "pct": clean_pct(value["pct"]), "count": count}}
    if key == "top_in":
        if not isinstance(value, dict) or set(value) != {"rank", "digits"}:
            raise ValueError("top_in needs exactly rank and digits")
        rank = value["rank"]
        if not is_int(rank) or not 1 <= rank <= 9:
            raise ValueError("rank must be a whole number from 1 to 9")
        return {"top_in": {"rank": rank, "digits": clean_digits(value["digits"])}}
    if key == "pointer_is_least_of":
        return {"pointer_is_least_of": clean_digits(value, 2)}
    raise ValueError(
        f"unknown condition '{key}'; use parity, digit_in, move, any, freq_below, freq_at_least, top_in or pointer_is_least_of"
    )


def clean_element(element):
    if isinstance(element, list):
        if not element:
            raise ValueError("a grouped trigger element cannot be empty")
        return [clean_condition(c) for c in element]
    return clean_condition(element)


def conditions_of(element):
    return element if isinstance(element, list) else [element]


def uses_freq(trigger):
    elements = list(trigger["seq"])
    if "then" in trigger:
        elements.append(trigger["then"]["cond"])
    return any(next(iter(c)) in FREQ_CONDITIONS for el in elements for c in conditions_of(el))


def clean_contract(contract):
    if not isinstance(contract, dict):
        raise ValueError("contract must be an object")
    kind = contract.get("type")
    side = contract.get("side")
    if kind == "even_odd":
        if side not in ("even", "odd"):
            raise ValueError("even_odd side must be 'even' or 'odd'")
        return {"type": kind, "side": side}
    if kind == "over_under":
        barrier = contract.get("barrier")
        if not is_int(barrier):
            raise ValueError("over_under needs a whole-number barrier")
        if side == "over" and 0 <= barrier <= 8:
            return {"type": kind, "side": side, "barrier": barrier}
        if side == "under" and 1 <= barrier <= 9:
            return {"type": kind, "side": side, "barrier": barrier}
        raise ValueError("over needs a barrier from 0 to 8, under needs a barrier from 1 to 9")
    if kind == "rise_fall":
        if side not in ("rise", "fall"):
            raise ValueError("rise_fall side must be 'rise' or 'fall'")
        return {"type": kind, "side": side}
    raise ValueError("contract type must be even_odd, over_under or rise_fall")


def validate_spec(raw):
    if not isinstance(raw, dict):
        raise ValueError("rule must be a JSON object")
    unknown = set(raw) - SPEC_KEYS
    if unknown:
        raise ValueError(f"unknown keys: {', '.join(sorted(unknown))}")
    symbols = raw.get("symbols")
    if not isinstance(symbols, list) or not symbols or not all(isinstance(s, str) and s for s in symbols):
        raise ValueError("symbols must be a non-empty list of symbol names")
    trigger_raw = raw.get("trigger", {"seq": []})
    if not isinstance(trigger_raw, dict) or set(trigger_raw) - {"seq", "then"}:
        raise ValueError("trigger must be an object with only 'seq' and optionally 'then'")
    seq = trigger_raw.get("seq", [])
    if not isinstance(seq, list) or len(seq) > MAX_SEQ:
        raise ValueError(f"trigger seq must be a list of at most {MAX_SEQ} elements")
    trigger = {"seq": [clean_element(el) for el in seq]}
    if "then" in trigger_raw:
        then = trigger_raw["then"]
        if not isinstance(then, dict) or set(then) != {"within", "cond"}:
            raise ValueError("then needs exactly 'within' and 'cond'")
        within = then["within"]
        if not is_int(within) or not 1 <= within <= 10:
            raise ValueError("within must be a whole number of ticks from 1 to 10")
        trigger["then"] = {"within": within, "cond": clean_element(then["cond"])}
    window = raw.get("window")
    needs_window = uses_freq(trigger)
    if needs_window and window is None:
        raise ValueError("frequency conditions need a window")
    if window is not None and not needs_window:
        raise ValueError("window is only allowed with frequency conditions")
    if window is not None and (not is_int(window) or not 20 <= window <= 2000):
        raise ValueError("window must be a whole number of ticks from 20 to 2000")
    contract = clean_contract(raw.get("contract"))
    duration = raw.get("duration", 1)
    if not is_int(duration) or not 1 <= duration <= 10:
        raise ValueError("duration must be a whole number of ticks from 1 to 10")
    margin = raw.get("margin", DEFAULT_MARGIN)
    if not is_number(margin) or not 0 <= margin < 0.2:
        raise ValueError("margin must be a number from 0 to 0.2")
    target = raw.get("target_trades", DEFAULT_TARGET)
    if not is_int(target) or not 1000 <= target <= 200000:
        raise ValueError("target_trades must be a whole number from 1000 to 200000")
    spec = {
        "symbols": sorted(set(symbols)),
        "trigger": trigger,
        "contract": contract,
        "duration": duration,
        "margin": float(margin),
        "target_trades": target,
    }
    if window is not None:
        spec["window"] = window
    return spec


def canonical(spec):
    return json.dumps(spec, sort_keys=True, separators=(",", ":"))


def spec_hash(spec):
    return hashlib.sha256(canonical(spec).encode("utf-8")).hexdigest()


def fair_probability(contract):
    if contract["type"] == "over_under":
        barrier = contract["barrier"]
        return (9 - barrier) / 10 if contract["side"] == "over" else barrier / 10
    return 0.5


def breakeven(contract, margin):
    return fair_probability(contract) / (1.0 - margin)


def binom_p(wins, trades, be):
    return float(stats.binomtest(int(wins), int(trades), be, alternative="greater").pvalue)


def mode_interval(epoch):
    values, counts = np.unique(np.diff(epoch), return_counts=True)
    return int(values[np.argmax(counts)])


def lookback(spec):
    seq = spec["trigger"]["seq"]
    conds = [c for el in seq for c in conditions_of(el)]
    extra = 1 if any("move" in c for c in conds) else 0
    base = max(len(seq) - 1 + extra, 0)
    window = spec.get("window")
    return base + (window - 1 if window else 0)


def freq_matrix(digit, window):
    return np.column_stack(
        [rolling_mean((digit == d).astype(np.float64), window) for d in range(10)]
    )


def condition_mask(cond, digit, quote, freq):
    key, value = next(iter(cond.items()))
    n = len(digit)
    if key == "parity":
        return (digit % 2) == (0 if value == "even" else 1)
    if key == "digit_in":
        return np.isin(digit, value)
    if key == "move":
        step = np.zeros(n, dtype=np.int64)
        step[1:] = np.sign(np.diff(quote)).astype(np.int64)
        return step == {"up": 1, "down": -1, "flat": 0}[value]
    if key == "freq_below":
        cols = freq[:, value["digits"]]
        return (cols < value["pct"] / 100.0 - EPS).all(axis=1)
    if key == "freq_at_least":
        cols = freq[:, value["digits"]]
        return (cols >= value["pct"] / 100.0 - EPS).sum(axis=1) >= value["count"]
    if key == "top_in":
        order = np.argsort(-freq, axis=1, kind="stable")[:, : value["rank"]]
        return np.isin(order, value["digits"]).all(axis=1) & np.isfinite(freq).all(axis=1)
    if key == "pointer_is_least_of":
        cols = freq[:, value]
        least = np.asarray(value)[np.argmin(cols, axis=1)]
        return (digit == least) & np.isfinite(cols).all(axis=1)
    return np.ones(n, dtype=bool)


def element_mask(element, digit, quote, freq):
    mask = np.ones(len(digit), dtype=bool)
    for cond in conditions_of(element):
        mask &= condition_mask(cond, digit, quote, freq)
    return mask


def trigger_mask(seq, digit, quote, freq):
    n = len(digit)
    k = len(seq)
    mask = np.ones(n, dtype=bool)
    for i, element in enumerate(seq):
        shift = k - 1 - i
        em = element_mask(element, digit, quote, freq)
        shifted = np.zeros(n, dtype=bool)
        shifted[shift:] = em[: n - shift]
        mask &= shifted
    return mask


def entry_ticks(trig, then, digit, quote, freq):
    if then is None:
        return trig
    n = len(digit)
    cm = element_mask(then["cond"], digit, quote, freq)
    entries = np.full(len(trig), -1, dtype=np.int64)
    for j in range(then["within"], 0, -1):
        pos = trig + j
        inside = pos < n
        hit = np.zeros(len(trig), dtype=bool)
        hit[inside] = cm[pos[inside]]
        entries = np.where(hit, pos, entries)
    return np.unique(entries[entries >= 0])


def outcome_win(contract, h, digit, quote):
    n = len(digit)
    kind, side = contract["type"], contract["side"]
    if kind == "rise_fall":
        win = np.zeros(n, dtype=bool)
        if side == "rise":
            win[: n - h] = quote[h:] > quote[: n - h]
        else:
            win[: n - h] = quote[h:] < quote[: n - h]
        return win
    exit_digit = np.zeros(n, dtype=np.int64)
    exit_digit[: n - h] = digit[h:]
    if kind == "even_odd":
        return (exit_digit % 2) == (0 if side == "even" else 1)
    barrier = contract["barrier"]
    return exit_digit > barrier if side == "over" else exit_digit < barrier


def find_trades(spec, epoch, quote, digit, interval, after_epoch):
    n = len(epoch)
    h = spec["duration"]
    then = spec["trigger"].get("then")
    within = then["within"] if then else 0
    back = lookback(spec)
    if n < back + within + h + 5:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=bool)
    window = spec.get("window")
    freq = freq_matrix(digit, window) if window else None
    valid = contiguous_span(epoch, interval, back, within + h) & (epoch > after_epoch)
    trig = np.flatnonzero(trigger_mask(spec["trigger"]["seq"], digit, quote, freq) & valid)
    entries = entry_ticks(trig, then, digit, quote, freq)
    win = outcome_win(spec["contract"], h, digit, quote)
    free = -1
    keep = []
    for t in entries:
        if t >= free:
            keep.append(t)
            free = t + h
    idx = np.array(keep, dtype=np.int64)
    return epoch[idx], win[idx]


def forward_trades(spec, data, after_epoch):
    epochs = []
    wins = []
    for symbol in spec["symbols"]:
        if symbol not in data:
            continue
        e, q, d = data[symbol]
        if len(e) < 20:
            continue
        t_epoch, t_win = find_trades(spec, e, q, d, mode_interval(e), after_epoch)
        epochs.append(t_epoch)
        wins.append(t_win)
    if not epochs:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=bool)
    ep = np.concatenate(epochs)
    w = np.concatenate(wins)
    order = np.argsort(ep, kind="stable")
    return ep[order], w[order]