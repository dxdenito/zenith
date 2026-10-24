import json
import os
from dataclasses import dataclass

import numpy as np
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.analysis_engine import SPLIT
from app.ml_features import build_features, feature_rows

TOP_Q = 0.10
FOLDS = 4
MIN_TRAIN = 5000
MIN_TRADES = 200
CUTOFF_FILE = "ml_cutoffs.json"


@dataclass
class Target:
    name: str
    horizon: int
    y: np.ndarray
    win_a: np.ndarray
    win_b: np.ndarray
    be_a: float
    be_b: float
    ref: float
    stride: np.ndarray
    trainable: np.ndarray


@dataclass
class MLResult:
    symbol: str
    target: str
    model: str
    n_disc: int
    rate_disc: float
    be_disc: float
    p_disc: float
    gain: float
    n_hold: int = 0
    rate_hold: float = 0.0
    be_hold: float = 0.0
    p_hold: float = 1.0
    survives_fdr: bool = False
    survives: bool = False


@dataclass
class Item:
    result: MLResult
    X: np.ndarray
    tg: Target
    disc: np.ndarray
    hold: np.ndarray
    kind: str


def load_cutoff(symbol, epoch, path=CUTOFF_FILE):
    data = {}
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    if symbol not in data:
        data[symbol] = int(epoch[int(SPLIT * len(epoch))])
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    return int(data[symbol])


def synthetic(n, lift, seed=7):
    rng = np.random.default_rng(seed)
    epoch = 1_700_000_000 + np.arange(n, dtype=np.int64) * 2
    quote = np.round(1000.0 * np.exp(np.cumsum(rng.normal(0.0, 1e-4, n))), 2)
    digit = rng.integers(0, 10, n)
    evens = rng.choice([0, 2, 4, 6, 8], n)
    odds = rng.choice([1, 3, 5, 7, 9], n)
    u = rng.random(n)
    for i in range(3, n):
        if digit[i - 1] % 2 == 1 and digit[i - 2] % 2 == 1 and digit[i - 3] % 2 == 1:
            digit[i] = evens[i] if u[i] < lift else odds[i]
    return epoch, quote, digit


def build_targets(s, margin, duration, barriers):
    n = len(s.digit)
    keep = 1.0 - margin
    everywhere = np.ones(n, dtype=bool)
    nxt = np.zeros(n, dtype=np.int64)
    nxt[:-1] = s.digit[1:]
    even = nxt % 2 == 0
    targets = [
        Target("Even/Odd", 1, even.astype(np.int8), even, ~even, 0.5 / keep, 0.5 / keep, 0.5, everywhere, everywhere)
    ]
    for k in barriers:
        over = nxt > k
        fa, fb = (9 - k) / 10, (k + 1) / 10
        targets.append(
            Target(
                f"Over {k}/Under {k + 1}", 1, over.astype(np.int8), over, ~over,
                fa / keep, fb / keep, fa, everywhere, everywhere,
            )
        )
    h = duration
    q = s.quote
    up = np.zeros(n, dtype=bool)
    down = np.zeros(n, dtype=bool)
    up[: n - h] = q[h:] > q[: n - h]
    down[: n - h] = q[h:] < q[: n - h]
    stride = (np.arange(n) % h) == 0
    targets.append(
        Target(f"Rise/Fall {h}t", h, up.astype(np.int8), up, down, 0.5 / keep, 0.5 / keep, 0.5, stride, up | down)
    )
    return targets


def make_model(kind):
    if kind == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=300))
    return HistGradientBoostingClassifier(
        max_iter=100,
        learning_rate=0.08,
        max_depth=4,
        min_samples_leaf=300,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=0,
    )


def fit_predict(kind, X, y, train, test):
    model = make_model(kind)
    model.fit(X[train], y[train])
    return model.predict_proba(X[test])[:, 1], float(y[train].mean())


def trade_sums(p, tg, rows):
    k = max(int(np.ceil(TOP_Q * len(p))), 1)
    pick = np.argsort(-np.abs(p - tg.ref), kind="stable")[:k]
    side_a = p[pick] > tg.ref
    r = rows[pick]
    wins = np.where(side_a, tg.win_a[r], tg.win_b[r])
    be = np.where(side_a, tg.be_a, tg.be_b)
    return np.array([len(pick), wins.sum(), be.sum(), (be * (1.0 - be)).sum()], dtype=float)


def finish(sums):
    n, w, e, v = sums
    z = (w - e) / np.sqrt(v) if v > 0 else 0.0
    return int(n), float(w / n), float(e / n), float(stats.norm.sf(z))


def log_loss_gain(y, p, base):
    p = np.clip(p, 1e-6, 1.0 - 1e-6)
    b = min(max(base, 1e-6), 1.0 - 1e-6)
    model = -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))
    ref = -(y * np.log(b) + (1.0 - y) * np.log(1.0 - b))
    return ref - model


def run_discovery(kind, X, tg, disc):
    m = len(disc)
    edges = np.linspace(0, m, FOLDS + 2).astype(int)
    sums = np.zeros(4)
    gains = []
    for i in range(1, FOLDS + 1):
        test = disc[edges[i] : edges[i + 1]]
        if test.size == 0:
            continue
        train = disc[disc < test[0] - tg.horizon]
        train = train[tg.trainable[train]]
        test = test[tg.stride[test]]
        if train.size < MIN_TRAIN or test.size == 0:
            continue
        p, base = fit_predict(kind, X, tg.y, train, test)
        sums += trade_sums(p, tg, test)
        usable = tg.trainable[test]
        gains.append(log_loss_gain(tg.y[test][usable].astype(float), p[usable], base))
    if sums[0] < MIN_TRADES or not gains:
        return None
    return finish(sums), float(np.concatenate(gains).mean())


def run_holdout(kind, X, tg, disc, hold):
    if hold.size == 0:
        return None
    train = disc[disc < hold[0] - tg.horizon]
    train = train[tg.trainable[train]]
    test = hold[tg.stride[hold]]
    if train.size < MIN_TRAIN or test.size == 0:
        return None
    p, _ = fit_predict(kind, X, tg.y, train, test)
    return finish(trade_sums(p, tg, test))


def evaluate_series(s, cutoff, kinds, barriers, margin, duration):
    X, _ = build_features(s.quote, s.digit)
    items = []
    for tg in build_targets(s, margin, duration, barriers):
        ok = feature_rows(s.epoch, X, s.interval, tg.horizon)
        disc = np.flatnonzero(ok & (s.epoch < cutoff))
        hold = np.flatnonzero(ok & (s.epoch >= cutoff))
        for kind in kinds:
            out = run_discovery(kind, X, tg, disc)
            print(f"  {s.symbol} {tg.name} {kind} done", flush=True)
            if out is None:
                continue
            (n, rate, be, p), gain = out
            items.append(Item(MLResult(s.symbol, tg.name, kind, n, rate, be, p, gain), X, tg, disc, hold, kind))
    return items


def finalize_ml(items):
    if not items:
        return []
    p = np.array([i.result.p_disc for i in items])
    order = np.argsort(p)
    m = len(p)
    limit = 0.05 * np.arange(1, m + 1) / m
    below = np.flatnonzero(p[order] <= limit)
    passed = np.zeros(m, dtype=bool)
    if below.size:
        passed[order[: below.max() + 1]] = True
    for item, flag in zip(items, passed):
        r = item.result
        r.survives_fdr = bool(flag)
        if not flag:
            continue
        out = run_holdout(item.kind, item.X, item.tg, item.disc, item.hold)
        if out is None:
            continue
        r.n_hold, r.rate_hold, r.be_hold, r.p_hold = out
        r.survives = r.p_hold < 0.05 and r.rate_hold > r.be_hold
    return [i.result for i in items]