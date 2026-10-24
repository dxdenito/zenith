import itertools
from dataclasses import dataclass

import numpy as np
from scipy import stats

SPLIT = 0.7
MIN_TRIALS = 300


@dataclass
class Series:
    symbol: str
    epoch: np.ndarray
    quote: np.ndarray
    digit: np.ndarray
    interval: int
    run: np.ndarray


@dataclass
class Result:
    symbol: str
    family: str
    name: str
    n_disc: int
    rate_disc: float
    p_disc: float
    n_hold: int
    rate_hold: float
    p_hold: float
    breakeven: float
    survives_fdr: bool = False
    survives: bool = False


def build_series(symbol, epoch, quote, digit) -> Series:
    epoch = np.asarray(epoch, dtype=np.int64)
    quote = np.asarray(quote, dtype=float)
    digit = np.asarray(digit, dtype=np.int64)
    gaps = np.diff(epoch)
    values, counts = np.unique(gaps, return_counts=True)
    interval = int(values[np.argmax(counts)])
    ok = gaps == interval
    run = np.zeros(len(epoch), dtype=np.int64)
    for i in range(1, len(epoch)):
        run[i] = run[i - 1] + 1 if ok[i - 1] else 0
    return Series(symbol, epoch, quote, digit, interval, run)


def quality(s: Series) -> dict:
    gaps = np.diff(s.epoch)
    broken = gaps != s.interval
    return {
        "ticks": int(len(s.epoch)),
        "from": int(s.epoch[0]),
        "to": int(s.epoch[-1]),
        "interval_s": s.interval,
        "contiguous_pct": float((~broken).mean() * 100),
        "gaps": int(broken.sum()),
        "largest_gap_s": int(gaps.max()),
    }


def spec(family, name_base, name_comp, mask, base, comp, ref, fair_base, fair_comp):
    return {
        "family": family,
        "names": (name_base, name_comp),
        "mask": mask,
        "base": base,
        "comp": comp,
        "ref": ref,
        "fair": (fair_base, fair_comp),
    }


def digit_specs(s: Series) -> list:
    d = s.digit
    nxt = d[1:]
    prev = d[:-1]
    n1 = len(nxt)
    run1 = s.run[1:]
    everywhere = np.ones(n1, dtype=bool)
    even = nxt % 2 == 0
    specs = [spec("even_odd", "Even", "Odd", everywhere, even, ~even, 0.5, 0.5, 0.5)]
    for k in range(0, 9):
        over = nxt > k
        specs.append(
            spec(
                "over_under",
                f"Over {k}",
                f"Under {k + 1}",
                everywhere,
                over,
                ~over,
                (9 - k) / 10,
                (9 - k) / 10,
                (k + 1) / 10,
            )
        )
    for j in range(10):
        mask = (prev == j) & (run1 >= 1)
        specs.append(
            spec(
                "even_odd",
                f"Even after digit {j}",
                f"Odd after digit {j}",
                mask,
                even,
                ~even,
                0.5,
                0.5,
                0.5,
            )
        )
    par = d % 2
    for length in range(2, 6):
        m = n1 - (length - 1)
        if m <= 0:
            continue
        same = np.ones(m, dtype=bool)
        for k in range(1, length):
            same &= par[length - 1 - k : length - 1 - k + m] == par[length - 1 : length - 1 + m]
        mask = np.zeros(n1, dtype=bool)
        mask[length - 1 :] = same
        mask &= run1 >= length
        continues = (nxt % 2) == par[:n1]
        specs.append(
            spec(
                "even_odd",
                f"Same parity after {length} in a row",
                f"Opposite parity after {length} in a row",
                mask,
                continues,
                ~continues,
                0.5,
                0.5,
                0.5,
            )
        )
    return specs


def rise_fall_specs(s: Series, h: int) -> list:
    q = s.quote
    n = len(q)
    m = n - h
    if m <= 4 * h + 10:
        return []
    up = q[h:] > q[:m]
    down = q[h:] < q[:m]
    runh = s.run[h : h + m]
    stride = (np.arange(m) % h) == 0
    dirs = np.sign(np.diff(q)).astype(np.int64)

    def back(i):
        arr = np.zeros(m, dtype=np.int64)
        arr[i + 1 :] = dirs[: m - i - 1]
        return arr

    specs = [spec("rise_fall", "Rise", "Fall", (runh >= h) & stride, up, down, 0.5, 0.5, 0.5)]
    for length in (1, 2, 3):
        backs = [back(i) for i in range(length)]
        for pattern in itertools.product((1, -1), repeat=length):
            mask = (runh >= h + length) & stride
            for i in range(length):
                mask &= backs[i] == pattern[length - 1 - i]
            label = "".join("U" if p == 1 else "D" for p in pattern)
            specs.append(
                spec(
                    "rise_fall",
                    f"Rise after {label}",
                    f"Fall after {label}",
                    mask,
                    up,
                    down,
                    0.5,
                    0.5,
                    0.5,
                )
            )
    past = np.zeros(m, dtype=np.int64)
    past[h:] = np.sign(q[h:m] - q[: m - h])
    for value, label in ((1, "a past rise"), (-1, "a past fall")):
        mask = (runh >= 2 * h) & stride & (past == value)
        specs.append(
            spec(
                "rise_fall",
                f"Rise after {label}",
                f"Fall after {label}",
                mask,
                up,
                down,
                0.5,
                0.5,
                0.5,
            )
        )
    return specs


def binom(wins, trials, p, alternative="two-sided") -> float:
    if trials <= 0:
        return 1.0
    return float(stats.binomtest(int(wins), int(trials), p, alternative=alternative).pvalue)


def evaluate(symbol, sp, margin):
    mask = sp["mask"]
    split = int(SPLIT * len(mask))
    idx = np.arange(len(mask))
    disc = mask & (idx < split)
    hold = mask & (idx >= split)
    base, comp = sp["base"], sp["comp"]
    trials_d = int((disc & (base | comp)).sum())
    if trials_d < MIN_TRIALS:
        return None
    base_d = int((disc & base).sum())
    p_d = binom(base_d, trials_d, sp["ref"])
    if base_d / trials_d >= sp["ref"]:
        win, ref, fair, name = base, sp["ref"], sp["fair"][0], sp["names"][0]
    else:
        win, ref, fair, name = comp, 1 - sp["ref"], sp["fair"][1], sp["names"][1]
    n_d = int(disc.sum())
    w_d = int((disc & win).sum())
    n_h = int(hold.sum())
    w_h = int((hold & win).sum())
    trials_h = int((hold & (base | comp)).sum())
    p_h = binom(w_h, trials_h, ref, "greater")
    return Result(
        symbol,
        sp["family"],
        name,
        n_d,
        w_d / n_d,
        p_d,
        n_h,
        w_h / n_h if n_h else 0.0,
        p_h,
        fair / (1 - margin),
    )


def analyze(s: Series, margin: float = 0.03, duration: int = 5, mode: str = "patterns") -> list:
    if mode == "time":
        specs = time_specs(s, duration)
    else:
        specs = digit_specs(s) + rise_fall_specs(s, duration)
    results = [evaluate(s.symbol, sp, margin) for sp in specs]
    return [r for r in results if r is not None]


def finalize(results: list) -> list:
    if not results:
        return results
    p = np.array([r.p_disc for r in results])
    order = np.argsort(p)
    m = len(p)
    limit = 0.05 * np.arange(1, m + 1) / m
    below = np.where(p[order] <= limit)[0]
    passed = np.zeros(m, dtype=bool)
    if below.size:
        passed[order[: below.max() + 1]] = True
    for r, flag in zip(results, passed):
        r.survives_fdr = bool(flag)
        r.survives = bool(flag and r.p_hold < 0.05 and r.rate_hold > r.breakeven)
    return results


def omnibus(s: Series) -> dict:
    total = len(s.digit)
    split = int(SPLIT * total)
    out = {}
    for label, lo, hi in (("discovery", 0, split), ("holdout", split, total)):
        d = s.digit[lo:hi]
        uniform = float(stats.chisquare(np.bincount(d, minlength=10)).pvalue)
        ok = s.run[lo:hi][1:] >= 1
        pairs = d[:-1][ok] * 10 + d[1:][ok]
        table = np.bincount(pairs, minlength=100).reshape(10, 10)
        dependence = float(stats.chi2_contingency(table)[1])
        out[label] = {"uniformity_p": uniform, "dependence_p": dependence}
    return out


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def time_features(epoch):
    return {
        "hour": (epoch // 3600) % 24,
        "minute": (epoch // 60) % 60,
        "second": epoch % 60,
        "weekday": ((epoch // 86400) + 3) % 7,
    }


def time_tag(feature, value):
    if feature == "hour":
        return f"at hour {value:02d} UTC"
    if feature == "minute":
        return f"at minute {value:02d}"
    if feature == "second":
        return f"at second {value:02d}"
    return f"on {WEEKDAYS[value]}"


def time_specs(s: Series, h: int) -> list:
    nxt = s.digit[1:]
    even = nxt % 2 == 0
    over4 = nxt > 4
    feats_digit = time_features(s.epoch[1:])
    q = s.quote
    m = len(q) - h
    specs = []
    has_rf = m > 4 * h + 10
    if has_rf:
        up = q[h:] > q[:m]
        down = q[h:] < q[:m]
        runh = s.run[h : h + m]
        stride = (np.arange(m) % h) == 0
        feats_rf = time_features(s.epoch[:m])
    for feature, size in (("hour", 24), ("minute", 60), ("second", 60), ("weekday", 7)):
        for value in range(size):
            tag = time_tag(feature, value)
            mask = feats_digit[feature] == value
            specs.append(spec("time_even_odd", f"Even {tag}", f"Odd {tag}", mask, even, ~even, 0.5, 0.5, 0.5))
            specs.append(spec("time_over_under", f"Over 4 {tag}", f"Under 5 {tag}", mask, over4, ~over4, 0.5, 0.5, 0.5))
            if has_rf:
                mask_rf = (feats_rf[feature] == value) & (runh >= h) & stride
                specs.append(spec("time_rise_fall", f"Rise {tag}", f"Fall {tag}", mask_rf, up, down, 0.5, 0.5, 0.5))
    return specs

def analyze(s: Series, margin: float = 0.03, duration: int = 5, mode: str = "patterns") -> list:
    if mode == "time":
        specs = time_specs(s, duration)
    else:
        specs = digit_specs(s) + rise_fall_specs(s, duration)
    results = [evaluate(s.symbol, sp, margin) for sp in specs]
    return [r for r in results if r is not None]