import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { money, pct, toneOf } from "../../lib/tradeFormat";
import { Tile } from "./atoms";

export default function MartingaleBox({ strategy, stake, enabled, setEnabled, cfg, setCfg, locked, allowed }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const m = Number(cfg.multiplier);
    const n = Number(cfg.max_steps);
    const valid = m >= 1.1 && m <= 3 && Number.isInteger(n) && n >= 2 && n <= 6;
    if (!enabled || !strategy || !(Number(stake) > 0) || !valid) {
      setPreview(null);
      return undefined;
    }
    let cancelled = false;
    const id = setTimeout(async () => {
      try {
        const data = await api.authed(
          `/trading/martingale/preview?strategy=${encodeURIComponent(strategy)}&stake=${Number(stake)}&multiplier=${m}&max_steps=${n}`
        );
        if (!cancelled) {
          setPreview(data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [enabled, strategy, stake, cfg.multiplier, cfg.max_steps]);

  const set = (key) => (e) => setCfg((c) => ({ ...c, [key]: e.target.value }));
  const smallestWin = preview ? Math.min(preview.first_step_win, preview.last_step_win) : 0;

  return (
    <div className="mt-4 rounded-3xl bg-bg p-4">
      <label className="flex items-center gap-3 font-extrabold">
        <input
          type="checkbox"
          checked={enabled}
          disabled={locked || !allowed}
          onChange={(e) => setEnabled(e.target.checked)}
          className="size-5"
        />
        Martingale staking {allowed ? "" : "(demo accounts only)"}
      </label>
      {enabled && (
        <div className="mt-3 space-y-3">
          <p className="rounded-2xl bg-honey p-3 text-xs font-extrabold text-ink">
            Martingale does not improve your odds. It raises how much you stake and turns many small wins into
            one large loss. The average loss per amount staked is the same as without it.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="text-xs font-extrabold text-muted">Multiplier after a loss</span>
              <input
                type="number"
                step="0.1"
                min="1.1"
                max="3"
                value={cfg.multiplier}
                onChange={set("multiplier")}
                disabled={locked}
                className="mt-1 h-11 w-full rounded-2xl bg-surface px-4 font-bold outline-none"
              />
            </label>
            <label className="block">
              <span className="text-xs font-extrabold text-muted">Max steps</span>
              <select
                value={cfg.max_steps}
                onChange={set("max_steps")}
                disabled={locked}
                className="mt-1 h-11 w-full rounded-2xl bg-surface px-4 font-bold outline-none"
              >
                {[2, 3, 4, 5, 6].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-extrabold text-muted">After the last loss</span>
              <select
                value={cfg.on_cap}
                onChange={set("on_cap")}
                disabled={locked}
                className="mt-1 h-11 w-full rounded-2xl bg-surface px-4 font-bold outline-none"
              >
                <option value="stop">Stop trading</option>
                <option value="reset">Reset to base stake</option>
              </select>
            </label>
          </div>
          {error && <p className="text-sm font-bold text-brand">{error}</p>}
          {preview && (
            <div className="space-y-3">
              <p className="text-sm font-extrabold">
                Stakes in a cycle: {preview.stakes.map((s) => s.toFixed(2)).join(" → ")}
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Tile
                  label="Worst case, one cycle"
                  value={money(-preview.worst_case_loss)}
                  valueClass="text-brand"
                />
                <Tile label="Chance of hitting the cap" value={pct(preview.chance_cap_hit, 2)} />
                <Tile label="Avg result per amount staked" value={pct(preview.expected_loss_per_staked, 2)} />
                <Tile label="Smallest win in a cycle" value={money(smallestWin)} valueClass={toneOf(smallestWin)} />
              </div>
              {!preview.recovers_every_step && (
                <p className="text-sm font-extrabold text-brand">
                  With this multiplier a win at a later step does not recover the earlier losses, so a cycle
                  can end in a loss even when it wins.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}