import numpy as np

LAGS = 10
WINDOWS = (20, 50, 100)
RUN_CAP = 15
BACK = max(WINDOWS)


def infer_interval(epoch):
    return int(np.median(np.diff(np.asarray(epoch, dtype=np.int64))))


def contiguous_span(epoch, interval, back, forward):
    epoch = np.asarray(epoch, dtype=np.int64)
    n = len(epoch)
    gaps = np.zeros(n, dtype=np.int64)
    gaps[1:] = (np.diff(epoch) != interval).astype(np.int64)
    cs = np.cumsum(gaps)
    ok = np.zeros(n, dtype=bool)
    if n > back + forward:
        t = np.arange(back, n - forward)
        ok[t] = (cs[t + forward] - cs[t - back]) == 0
    return ok


def lag(a, k):
    out = np.full(len(a), np.nan)
    if k == 0:
        out[:] = a
    else:
        out[k:] = a[:-k]
    return out


def rolling_mean(a, w):
    c = np.cumsum(np.insert(np.asarray(a, dtype=np.float64), 0, 0.0))
    out = np.full(len(a), np.nan)
    out[w - 1:] = (c[w:] - c[:-w]) / w
    return out


def run_length(v, cap):
    n = len(v)
    idx = np.arange(n)
    change = np.ones(n, dtype=bool)
    change[1:] = v[1:] != v[:-1]
    start = np.maximum.accumulate(np.where(change, idx, 0))
    return np.minimum(idx - start + 1, cap).astype(np.float64)


def build_features(quote, digit):
    quote = np.asarray(quote, dtype=np.float64)
    digit = np.asarray(digit, dtype=np.int64)
    n = len(digit)
    parity = (digit % 2).astype(np.float64)
    digit_f = digit.astype(np.float64)
    logq = np.log(quote)
    ret = np.zeros(n)
    ret[1:] = np.diff(logq)
    sign = np.sign(ret)
    columns = {}
    with np.errstate(divide="ignore", invalid="ignore"):
        for k in range(LAGS):
            columns[f"parity_l{k}"] = lag(parity, k)
            columns[f"digit_l{k}"] = lag(digit_f, k)
            columns[f"sign_l{k}"] = lag(sign, k)
        vol = {
            w: np.sqrt(np.maximum(rolling_mean(ret ** 2, w) - rolling_mean(ret, w) ** 2, 0.0))
            for w in WINDOWS
        }
        long_vol = np.where(vol[BACK] > 0, vol[BACK], np.nan)
        for k in range(5):
            columns[f"absret_l{k}"] = lag(np.abs(ret), k) / long_vol
        columns["parity_run"] = run_length(parity.astype(np.int64), RUN_CAP)
        columns["sign_run"] = run_length(sign.astype(np.int64), RUN_CAP)
        for w in WINDOWS:
            wv = np.where(vol[w] > 0, vol[w], np.nan)
            columns[f"even_rate_{w}"] = 1.0 - rolling_mean(parity, w)
            columns[f"mean_digit_{w}"] = rolling_mean(digit_f, w)
            columns[f"vol_{w}"] = vol[w]
            columns[f"trend_{w}"] = (logq - lag(logq, w)) / (wv * np.sqrt(w))
        columns["vol_ratio"] = vol[WINDOWS[0]] / long_vol
        for d in range(10):
            columns[f"freq_{d}_{BACK}"] = rolling_mean((digit == d).astype(np.float64), BACK)
    names = list(columns)
    X = np.column_stack([columns[c] for c in names]).astype(np.float32)
    return X, names


def feature_rows(epoch, X, interval, forward):
    ok = contiguous_span(epoch, interval, BACK, forward)
    return ok & np.isfinite(X).all(axis=1)