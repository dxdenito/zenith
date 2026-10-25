import numpy as np

from app.ml_features import contiguous_span
from app.register_rules import entry_ticks, freq_matrix, lookback, trigger_mask


def live_signal(spec, epoch, quote, digit, interval):
    n = len(epoch)
    then = spec["trigger"].get("then")
    within = then["within"] if then else 0
    need = lookback(spec) + within
    if n < need + 5:
        return False
    if not contiguous_span(epoch, interval, need, 0)[n - 1]:
        return False
    window = spec.get("window")
    freq = freq_matrix(digit, window) if window else None
    trig = trigger_mask(spec["trigger"]["seq"], digit, quote, freq)
    if then is None:
        return bool(trig[n - 1])
    start = max(0, n - 1 - within)
    candidates = np.flatnonzero(trig[start : n - 1]) + start
    if candidates.size == 0:
        return False
    entries = entry_ticks(candidates, then, digit, quote, freq)
    return bool((entries == n - 1).any())