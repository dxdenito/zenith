# Zenith
 
**Status: archived (October 2026).** Zenith was a research and trading platform for Deriv synthetic indices. The research phase finished with a clear negative result: no strategy, prediction method or staking system beat the house. The platform is kept as a working, demo-first reference and as a reusable testing harness.
 
> **Disclaimer.** Zenith is an educational research tool, not financial advice. Every strategy in it tested as no better than the house margin. Expect to lose money. Real-money trading is off by default and should stay off. You are solely responsible for any trade placed through your account.
 
## What Zenith is
 
- A multi-tenant web app (FastAPI, React, PostgreSQL) that links Deriv accounts through OAuth, streams and stores ticks, and shows live markets.
- A statistical research harness: pattern and time analysis, a machine-learning check, a pre-registered hypothesis register with forward testing, offline backtests, a pricing scan, and martingale and session simulators.
- A demo-first trading engine that runs a chosen strategy on live ticks, with server-enforced limits and heavy disclaimers.
## Headline result
 
Deriv's synthetic indices are generated randomly, and every contract pays less than the true odds. Everything tried confirmed it:
 
| Question | Method | Result |
|---|---|---|
| Do digit or tick-direction patterns predict the next outcome? | `analyze.py` patterns mode, multiple-testing correction, pinned holdout | No test survived correction and holdout |
| Does time of day, minute or weekday matter? | `analyze.py` time mode | No test survived correction and holdout |
| Can a model find structure in the last 100 ticks? | `ml_check.py`: logistic regression and gradient boosting, walk-forward, top-10% confidence trades, correction across tests | No model survived. A planted rule (56% even after three odds) was detected, and a noise control was clean, so the harness works |
| Does an outside over/under strategy (digit-frequency regime) work? | `backtest.py`, windows 50 to 500 ticks, Over 3 and Over 2 regimes | 0 of 10 tests passed correction. Win rates sat at the plain fair rate, below break-even |
| Is any contract mispriced? | `pricing_scan.py` (public `proposal` quotes) | No. Margins were identical across symbols and durations and none was at or below zero |
| Does martingale change the odds? | `martingale_check.py` on 327k trades | No. Win rate at every step was about 50%. It staked 2.1 times as much as flat staking and lost about 2.4 times as much on the same trades |
| Does a profit target per session help? | `session_check.py` | It raises the chance of a winning session and makes a losing one more expensive. The expected result stays negative |
 
Quoted margins (stake 10, unauthenticated quotes, October 2026):
 
| Contract | Margin | Win rate needed |
|---|---|---|
| Even / odd, most over/under barriers | 2.35% | about 51.2% for even/odd |
| Over 0, Under 9, Differs | 1.36% | 91.24% |
| Over 8, Under 1, Matches | 10.71% | 11.20% |
| Rise / fall (5 to 10 ticks) | about 2.4% to 3.5% | depends on the tie rate |
 
Why a target or a staking system cannot fix it: every trade has negative expected value, so any rule for when to stop or how much to stake leaves the expected total negative. A cap or target only changes the shape of the loss: many small wins and a rare large loss. Short samples hide the rare loss, so deep-step martingale runs can look profitable in history and are not.
 
## Repository layout
 
Backend (`backend/`):
 
- `app/main.py`: app startup, collector, bot manager.
- `app/collector.py`, `app/market_sync.py`: live tick streaming and symbol sync from Deriv's public WebSocket.
- `app/deriv_oauth.py`, `app/routers/accounts.py`: OAuth (PKCE) linking and account switching.
- `app/analysis_engine.py`: pattern and time tests, correction, holdout.
- `app/ml_features.py`, `app/ml_engine.py`: features, walk-forward models, the planted-rule control.
- `app/register_rules.py`, `app/register_models.py`: rule specs as JSON, trigger vocabulary, forward-test statistics.
- `app/strategies.py`, `app/live_signal.py`, `app/trade_engine.py`, `app/trade_models.py`, `app/routers/trading.py`: strategy catalogue, live signals, the bot, trade storage, trading API.
Command-line tools (`backend/`):
 
| Tool | Purpose |
|---|---|
| `analyze.py` | pattern and time analysis |
| `ml_check.py` | machine-learning check and controls |
| `register.py` | hypothesis register: `init`, `add`, `list`, `show`, `run` |
| `backtest.py` | offline scan of a rule across lookback windows |
| `fill_gaps.py` | fills holes in stored ticks from Deriv history |
| `pricing_scan.py` | quotes every contract type and computes margins |
| `martingale_check.py` | martingale simulation on history or on stored demo trades |
| `session_check.py` | hourly-session simulation with a profit target |
| `add_step_column.py` | one-off migration for the `trades.step` column |
 
Frontend (`frontend/src/`): Markets, Trade and Settings pages. Settings has Profile, Account, Trading and Appearance tabs. Trade components live in `components/trade/`, with the loading and polling logic in `lib/useTrading.js`.
 
## Running it
 
1. Create a PostgreSQL database and a `.env` for the backend (database URL, JWT secret, Fernet encryption key, Deriv app ID, redirect URI and scopes, frontend URL and cookie settings; see `app/config.py`). Tables are created on startup. Databases created before the martingale feature need `python add_step_column.py` once.
2. Install the backend requirements, then start the API (for example `uvicorn app.main:app --reload`).
3. In `frontend/`: `npm install` then `npm run dev`.
4. Register, link a Deriv account in Settings, and add markets on the Markets page so ticks stream.
Typical research commands (from `backend/`):
 
```
python analyze.py R_100 R_50 1HZ100V --mode patterns
python ml_check.py --control 0.56 --barriers 4
python ml_check.py R_100 --margin 0.0235
python fill_gaps.py R_100 R_50
python register.py init
python register.py add rules/even_after_odd.json
python register.py run
python backtest.py rules/over3_regime.json rules/over2_regime.json --windows 50 100 200 300 500
python pricing_scan.py R_100 R_50 1HZ100V
python martingale_check.py history rules/even_after_odd.json --symbols R_100 --multiplier 2 --steps 4
python session_check.py rules/even_after_odd.json --symbols R_100 --target 5 --steps 4
```
 
Run `fill_gaps.py` with the server stopped. The server must be running for ticks to stream, so stored history has gaps wherever it was off.
 
## Trading safeguards
 
- **Demo first.** A real account is refused unless live trading is enabled in Settings, and enabling it needs the workspace owner role, an accepted disclaimer and the typed phrase `ENABLE LIVE TRADING`. The server decides the account type from the database, never from the frontend.
- **Server-side limits, re-checked before every trade:** maximum stake, daily loss limit (UTC day), trades per hour, and losses in a row. The lower of the user's setting and a built-in cap applies. Built-in caps for real accounts: stake 5, daily loss 20, 120 trades per hour, 10 losses in a row. For demo: 100, 1000, 600, 50.
- **Martingale is demo only** (`MARTINGALE_MODES` in `app/strategies.py`), limited to 2 to 6 steps with a multiplier of 1.1 to 3. A start is refused if the largest stake exceeds the stake limit or one full losing cycle exceeds the daily loss limit. The cap action is user-set: stop trading or reset to the base stake.
- **Session targets** require martingale so every session has a defined worst case. The preview simulates the chance of reaching the target, the chance of hitting the cap and the expected result per session, which is negative.
- **Versioned disclaimer.** Changing `DISCLAIMER_VERSION` forces every user to accept it again.
- **One bot per user, one contract at a time.** Open contracts the engine cannot confirm are marked `unknown` and stop the bot.
## Deriv API notes
 
- Proposals use `underlying_symbol`, not `symbol`.
- Trading needs a one-time WebSocket URL from a REST call with the account token and the app ID. The URL is short-lived and single-use, so every reconnect needs a new one.
- `proposal`, `proposal_open_contract`, `buy` and `sell` share a rate limit of 360 calls per minute. `pricing_scan.py` paces itself and retries when limited.
- Quotes through the public socket may differ from what an authorised account is quoted. Compare one before relying on any figure.
## Known limitations and unverified items
 
- **Alignment.** Backtests assume entry at the last seen tick and exit at tick `t + duration`. A real contract enters on the first tick after purchase. The engine stores `signal_epoch` and `entry_epoch` on each trade, so a batch of demo trades settles the question. It was not reviewed at archive time.
- **Forward test.** Rule #1 ("Even after odd") was registered 2026-10-24 08:00 UTC with a target of 6000 trades. Run `python register.py run` to see whether it has concluded. It was expected to fail.
- **Margins.** Default margins in rules are 2.35%. Use the scan figure for other contracts.
- **Data coverage.** Stored ticks cover only the periods when the server was running or when history was backfilled.
- **Code status.** The trade engine, register, pricing scan and simulators were written to be tested by their owner on demo. Treat them as reference code, not production-ready software, and do not use them with real money.
## Lessons carried forward
 
The testing harness is reusable on any price series:
 
1. Pin the discovery and holdout cutoff once, so repeated runs cannot leak the holdout into discovery.
2. Write every rule as an immutable, hashed spec before testing, and never delete failed ones, so the correction counts every attempt.
3. Forward-test on data that did not exist when the rule was written, with a sample size fixed in advance and a single look.
4. Include a planted-rule control and a pure-noise control, so a null result means something.
5. Test against the real cost of trading, measured from quotes, not an assumed one.
6. Distrust results that depend on rare events appearing in a short sample.
The planned next project applies this harness to forex, where real market structure can exist and costs are spreads and commissions instead of a fixed house margin.