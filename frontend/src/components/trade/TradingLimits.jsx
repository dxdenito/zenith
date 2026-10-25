import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { ShieldAlert } from "lucide-react";
import { api } from "../../lib/api";

const LIMITS = [
  ["max_stake", "Max stake per trade", "0.01"],
  ["daily_loss_cap", "Daily loss limit", "0.01"],
  ["max_trades_per_hour", "Max trades per hour", "1"],
  ["max_consecutive_losses", "Stop after losses in a row", "1"],
];

export default function TradingLimits() {
  const [settings, setSettings] = useState(null);
  const [values, setValues] = useState({});
  const [liveText, setLiveText] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setSettings(await api.authed("/trading/settings"));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (settings) {
      setValues(Object.fromEntries(LIMITS.map(([key]) => [key, String(settings[key])])));
    }
  }, [settings]);

  async function patch(body, done) {
    setBusy(true);
    setMsg("");
    setError("");
    try {
      setSettings(await api.authed("/trading/settings", { method: "PATCH", body }));
      if (done) done();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const saveLimits = () =>
    patch(Object.fromEntries(LIMITS.map(([key]) => [key, Number(values[key])])), () => setMsg("Saved."));

  const canEnable =
    settings && settings.can_enable_live && settings.acknowledged && liveText === settings.live_confirmation;

  return (
    <section className="rounded-[32px] bg-surface p-5 shadow-soft">
      <div className="flex items-center gap-3">
        <span className="grid size-12 shrink-0 place-items-center rounded-full bg-honey text-ink">
          <ShieldAlert className="size-6" strokeWidth={2.4} />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-xl font-bold">Trading limits</h2>
          <p className="text-sm font-semibold text-muted">
            The server enforces these before every trade. Trading itself happens on the{" "}
            <Link to="/trade" className="underline">
              Trade
            </Link>{" "}
            page.
          </p>
        </div>
      </div>

      {error && (
        <p className="mt-4 rounded-3xl bg-brand/10 px-5 py-3 text-sm font-bold text-brand">{error}</p>
      )}

      {!settings && !error && <div className="mt-4 h-24 animate-pulse rounded-3xl bg-bg" />}

      {settings && (
        <>
          <p className="mt-4 text-sm font-semibold text-muted">
            The server uses the lower of your limit and its built-in cap for the account type.
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {LIMITS.map(([key, label, step]) => (
              <label key={key} className="block">
                <span className="text-xs font-extrabold text-muted">{label}</span>
                <input
                  type="number"
                  step={step}
                  min="0"
                  value={values[key] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                  className="mt-1 h-11 w-full rounded-2xl bg-bg px-4 font-bold outline-none"
                />
                <span className="text-[11px] font-bold text-muted">
                  built-in cap: {settings.hard_limits.demo[key]} demo · {settings.hard_limits.real[key]} real
                </span>
              </label>
            ))}
          </div>
          <motion.button
            type="button"
            whileTap={{ scale: 0.96 }}
            disabled={busy}
            onClick={saveLimits}
            className="mt-4 h-11 rounded-full bg-brand px-6 font-extrabold text-on-brand disabled:opacity-60"
          >
            Save limits
          </motion.button>
          {msg && <p className="mt-2 text-sm font-bold text-muted">{msg}</p>}

          <div className="mt-6 rounded-3xl bg-bg p-4">
            <p className="font-display text-lg font-bold">
              Live trading is {settings.live_enabled ? "ON" : "OFF"}
            </p>
            {settings.live_enabled ? (
              <motion.button
                type="button"
                whileTap={{ scale: 0.96 }}
                disabled={busy}
                onClick={() => patch({ live_enabled: false })}
                className="mt-3 h-11 rounded-full bg-text px-6 font-extrabold text-bg disabled:opacity-60"
              >
                Turn live trading off
              </motion.button>
            ) : (
              <div className="mt-2 space-y-3">
                <p className="text-sm font-semibold text-muted">
                  Real-money trading stays blocked on the server until you enable it here.
                  {!settings.can_enable_live && " Only the workspace owner can do this."}
                  {!settings.acknowledged && " Accept the risk disclaimer on the Trade page first."}
                </p>
                <input
                  type="text"
                  value={liveText}
                  onChange={(e) => setLiveText(e.target.value)}
                  placeholder={`Type ${settings.live_confirmation}`}
                  className="h-11 w-full rounded-2xl bg-surface px-4 font-bold outline-none"
                />
                <motion.button
                  type="button"
                  whileTap={{ scale: 0.96 }}
                  disabled={busy || !canEnable}
                  onClick={() => patch({ live_enabled: true, confirm_text: liveText }, () => setLiveText(""))}
                  className="h-11 rounded-full bg-brand px-6 font-extrabold text-on-brand disabled:opacity-50"
                >
                  Enable live trading
                </motion.button>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}