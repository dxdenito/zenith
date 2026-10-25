import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { Play } from "lucide-react";
import MartingaleBox from "./MartingaleBox";

export default function StartPanel({ strategy, active, mode, running, busy, onStart }) {
  const [symbol, setSymbol] = useState("");
  const [stake, setStake] = useState("1");
  const [mg, setMg] = useState(false);
  const [mgCfg, setMgCfg] = useState({ multiplier: "2", max_steps: "4", on_cap: "stop" });

  useEffect(() => {
    if (!strategy.symbols.some((s) => s.symbol === symbol)) {
      setSymbol(strategy.symbols[0]?.symbol ?? "");
    }
  }, [strategy, symbol]);

  useEffect(() => {
    if (mode !== "demo") setMg(false);
  }, [mode]);

  function submit() {
    onStart({
      strategy: strategy.key,
      symbol,
      stake: Number(stake),
      martingale: mg
        ? {
            multiplier: Number(mgCfg.multiplier),
            max_steps: Number(mgCfg.max_steps),
            on_cap: mgCfg.on_cap,
          }
        : null,
    });
  }

  return (
    <section className="rounded-[32px] bg-surface p-5 shadow-soft">
      <h2 className="font-display text-xl font-bold">Start</h2>
      {active && (
        <p className="mt-1 text-sm font-bold text-muted">
          Account {active.deriv_account_id} · {active.currency ?? "—"} · {mode}
        </p>
      )}
      {mode === "real" && (
        <p className="mt-2 rounded-2xl bg-brand/10 p-3 text-sm font-extrabold text-brand">
          This is a real-money account. The server refuses to start unless live trading is enabled in{" "}
          <Link to="/settings" className="underline">
            Settings
          </Link>
          .
        </p>
      )}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-extrabold text-muted">Market</span>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            disabled={running}
            className="mt-1 h-11 w-full rounded-2xl bg-bg px-4 font-bold outline-none"
          >
            {strategy.symbols.length === 0 && <option value="">No streaming market fits</option>}
            {strategy.symbols.map((s) => (
              <option key={s.symbol} value={s.symbol}>
                {s.name} ({s.symbol})
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-extrabold text-muted">Stake per trade</span>
          <input
            type="number"
            step="0.01"
            min="0"
            value={stake}
            onChange={(e) => setStake(e.target.value)}
            disabled={running}
            className="mt-1 h-11 w-full rounded-2xl bg-bg px-4 font-bold outline-none"
          />
        </label>
      </div>
      <MartingaleBox
        strategy={strategy.key}
        stake={stake}
        enabled={mg}
        setEnabled={setMg}
        cfg={mgCfg}
        setCfg={setMgCfg}
        locked={running}
        allowed={mode === "demo"}
      />
      <motion.button
        type="button"
        whileTap={{ scale: 0.96 }}
        disabled={busy || running || !active || !symbol || !(Number(stake) > 0)}
        onClick={submit}
        className="mt-4 flex h-12 items-center gap-2 rounded-full bg-brand px-6 font-extrabold text-on-brand disabled:opacity-50"
      >
        <Play className="size-4" strokeWidth={3} />
        Start trading
      </motion.button>
      <p className="mt-2 text-xs font-bold text-muted">
        The bot places one trade at a time and stops on its own at your limits. Limits are in{" "}
        <Link to="/settings?tab=trading" className="underline">
          Settings
        </Link>
        .
      </p>
    </section>
  );
}