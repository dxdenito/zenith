from app.register_rules import breakeven, fair_probability, validate_spec

DISCLAIMER_VERSION = "2026-10-24-2"
LIVE_CONFIRMATION = "ENABLE LIVE TRADING"

DISCLAIMER_POINTS = [
    "Zenith is an educational research tool. It is not financial advice.",
    "Every strategy in Zenith was tested on historical data and none showed an edge over the house. Deriv's synthetic indices are generated randomly, and every contract pays less than the true odds.",
    "Expect to lose money. Over many trades the average result is a loss of roughly 1% to 3% of the amount staked on each trade. Some contracts win often but lose heavily on the rare loss, and a run of losses can wipe out a balance quickly.",
    "Past results, including any winning streak you see, do not predict the next trade.",
    "Trading starts on demo accounts only. Real-money trading stays off until you switch it on in Settings, and the server enforces your limits whatever the app shows.",
    "The software can contain errors, lose its connection, or fail to place, track or close a trade. You are solely responsible for every trade placed through your account.",
    "Never trade money you cannot afford to lose. If trading is causing you stress or harm, stop and seek help.",
        "Staking systems such as martingale do not improve your odds. They increase how much you stake, win small amounts often, and lose a large amount on a losing streak. The average loss per amount staked stays the same, and the total you stake goes up.",
]


def build(key, name, summary, raw, tested):
    spec = validate_spec(raw)
    be = breakeven(spec["contract"], spec["margin"])
    return {
        "key": key,
        "name": name,
        "summary": summary,
        "tested": tested.format(be=f"{be * 100:.1f}%"),
        "spec": spec,
        "break_even": be,
    }


_entries = [
    build(
        "even_after_odd",
        "Even after odd",
        "Waits for the last digit to be odd, then buys Even for 1 tick.",
        {
            "symbols": ["R_100"],
            "trigger": {"seq": [{"parity": "odd"}]},
            "contract": {"type": "even_odd", "side": "even"},
            "duration": 1,
            "margin": 0.0235,
        },
        "Tested on stored history with pattern analysis and a machine-learning check. No edge survived correction and holdout. At the quoted payout you need to win about {be} of trades to break even, while a fair even or odd call wins 50%.",
    ),
    build(
        "over3_regime",
        "Over 3 digit-frequency regime",
        "When digits 0 to 3 are each under 10% of the last 100 ticks and the most common digits are 4 to 9, waits for the least common of 1, 2 and 3, then buys Over 3 for 1 tick after a 4 to 8 within 2 ticks.",
        {
            "symbols": ["R_100"],
            "window": 100,
            "trigger": {
                "seq": [
                    [
                        {"freq_below": {"digits": [0, 1, 2, 3], "pct": 10.0}},
                        {"freq_at_least": {"digits": [4, 5, 6, 7, 8, 9], "pct": 11.0, "count": 2}},
                        {"top_in": {"rank": 2, "digits": [4, 5, 6, 7, 8, 9]}},
                        {"pointer_is_least_of": [1, 2, 3]},
                    ]
                ],
                "then": {"within": 2, "cond": {"digit_in": [4, 5, 6, 7, 8]}},
            },
            "contract": {"type": "over_under", "side": "over", "barrier": 3},
            "duration": 1,
            "margin": 0.0235,
        },
        "Scanned over five lookback windows from 50 to 500 ticks on stored history. None beat break-even: win rates sat near the plain 60% for Over 3 and below the roughly {be} needed.",
    ),
]

CATALOGUE = {entry["key"]: entry for entry in _entries}


def deriv_contract(contract):
    kind, side = contract["type"], contract["side"]
    if kind == "even_odd":
        return ("DIGITEVEN" if side == "even" else "DIGITODD"), None
    if kind == "over_under":
        return ("DIGITOVER" if side == "over" else "DIGITUNDER"), contract["barrier"]
    return ("CALL" if side == "rise" else "PUT"), None


def contract_label(spec):
    contract = spec["contract"]
    h = spec["duration"]
    ticks = f"{h} tick" + ("" if h == 1 else "s")
    if contract["type"] == "over_under":
        base = f"{contract['side'].capitalize()} {contract['barrier']}"
    else:
        base = contract["side"].capitalize()
    return f"{base}, {ticks}"

MARTINGALE_MODES = {"demo"}


def cycle_stakes(base, multiplier, steps):
    return [round(base * multiplier**k, 2) for k in range(steps)]


def martingale_preview(entry, base, multiplier, steps):
    fair = fair_probability(entry["spec"]["contract"])
    ratio = 1.0 / entry["break_even"]
    stakes = cycle_stakes(base, multiplier, steps)
    reach = 1.0
    lost = 0.0
    expected = 0.0
    staked = 0.0
    wins = []
    for stake in stakes:
        profit_if_win = stake * (ratio - 1.0) - lost
        wins.append(profit_if_win)
        expected += reach * fair * profit_if_win
        staked += reach * stake
        lost += stake
        reach *= 1.0 - fair
    expected -= reach * lost
    return {
        "stakes": stakes,
        "worst_case_loss": round(lost, 2),
        "chance_cap_hit": reach,
        "expected_per_cycle": expected,
        "expected_staked_per_cycle": staked,
        "expected_loss_per_staked": expected / staked if staked else 0.0,
        "first_step_win": wins[0],
        "last_step_win": wins[-1],
        "recovers_every_step": min(wins) > 0,
    }