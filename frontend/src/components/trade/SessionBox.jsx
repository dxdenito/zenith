import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { money, pct, toneOf } from "../../lib/tradeFormat";
import { Tile } from "./atoms";

const WINDOWS = [5, 15, 30, 60, 120, 240];

export default function SessionBox({ strategy, stake, mgCfg, enabled, setEnabled, cfg, setCfg, locked, available }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const m = Number(mgCfg.multiplier);
    const n = Number(mgCfg.max_steps);
    const target = Number(cfg.target);
    const ok =
      enabled &&
      available &&
      strategy &&
      Number(stake) > 0 &&
      m >= 1.1 &&
      m <= 3 &&
      n >= 2 &&
      n <= 6 &&
      target > 0 &&
      target <= 100 * Number(stake);
    if (!ok) {
      setPreview(null);
      return undefined;
    }
    let cancelled = false;
    const id = setTimeout(async () => {
      try {
        const data = await api.authed(
          `/trading/martingale/preview?strategy=${encodeURIComponent(strategy)}&stake=${Number(stake)}&multiplier=${m}&max_steps=${n}&target=${target}`
        );
        if (!cancelled) {
          setPreview(data.session);
          setError("");
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [enabled, available, strategy, stake, mgCfg.multiplier, mgCfg.max_steps, cfg.target]);

  const set = (key) => (e) => setCfg((c) => ({ ...c, [key]: e.target.value }));
  const perDay = preview ? preview.expected_per_session * (1440 / Number(cfg.window_minutes)) : null;

  return (
    <div className="mt-4 rounded-3xl bg-bg p-4">
      <label className="flex items-center gap-3 font-extrabold">
        <input
          type="checkbox"
          checked={enabled}
          disabled={locked || !available}
          onChange={(e) => setEnabled(e.target.checked)}
          className="size-5"
        />
        Session target {available ? "" : "(turn on martingale first)"}
      </label>
      {enabled && (
        <div className="mt-3 space-y-3">
          <p className="rounded-2xl bg-honey p-3 text-xs font-extrabold text-ink">
            A target changes how often a session ends in profit, not whether you lose. The expected result per
            session stays negative because the house margin applies to every trade.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="text-xs font-extrabold text-muted">Target per session</span>
              <input
                type="number"
                step="0.5"
                min="0"
                value={cfg.target}
                onChange={set("target")}
                disabled={locked}
                className="mt-1 h-11 w-full rounded-2xl bg-surface px-4 font-bold outline-none"
              />
            </label>
            <label className="block">
              <span className="text-xs font-extrabold text-muted">Session length</span>
              <select
                value={cfg.window_minutes}
                onChange={set("window_minutes")}
                disabled={locked}
                className="mt-1 h-11 w-full rounded-2xl bg-surface px-4 font-bold outline-none"
              >
                {WINDOWS.map((w) => (
                  <option key={w} value={w}>
                    {w} min
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-extrabold text-muted">When the target is reached</span>
              <select
                value={cfg.on_target}
                onChange={set("on_target")}
                disabled={locked}
                className="mt-1 h-11 w-full rounded-2xl bg-surface px-4 font-bold outline-none"
              >
                <option value="rest">Rest until the next session</option>
                <option value="stop">Stop trading</option>
              </select>
            </label>
          </div>
          {error && <p className="text-sm font-bold text-brand">{error}</p>}
          {preview && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Tile label="Chance of reaching the target" value={pct(preview.chance_target)} />
                <Tile label="Chance of hitting the cap" value={pct(preview.chance_cap)} />
                <Tile
                  label="Expected per session"
                  value={money(preview.expected_per_session)}
                  valueClass={toneOf(preview.expected_per_session)}
                />
                <Tile
                  label="Average when target reached"
                  value={money(preview.avg_when_target)}
                  valueClass={toneOf(preview.avg_when_target)}
                />
                <Tile
                  label="Average when cap hit"
                  value={money(preview.avg_when_cap)}
                  valueClass={toneOf(preview.avg_when_cap)}
                />
                <Tile label="Worst 5% of sessions" value={money(preview.p5)} valueClass={toneOf(preview.p5)} />
              </div>
              <p className="text-xs font-bold text-muted">
                Simulated over {preview.runs.toLocaleString()} sessions. Expected per day if every{" "}
                {cfg.window_minutes}-minute window ran a session: {money(perDay)}. The expected figure comes from
                the margin; the simulated average was {money(preview.simulated_mean)} ± {preview.simulated_error.toFixed(2)}.
                The preview ignores the time limit, so it fits a strategy that trades often.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}