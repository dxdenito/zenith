import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Chip } from "../components/trade/atoms";
import LivePanel from "../components/trade/LivePanel";
import ResultsPanel from "../components/trade/ResultsPanel";
import RiskGate from "../components/trade/RiskGate";
import StartPanel from "../components/trade/StartPanel";
import StrategyPicker from "../components/trade/StrategyPicker";
import TradeList from "../components/trade/TradeList";
import { useAccounts } from "../context/AccountContext";
import { useTrading } from "../lib/useTrading";

export default function Trade() {
  const { active } = useAccounts();
  const { disclaimer, strategies, session, trades, stats, error, busy, acknowledge, start, stop } =
    useTrading(active?.id);
  const [pick, setPick] = useState(null);

  useEffect(() => {
    if (strategies && strategies.length > 0 && !pick) setPick(strategies[0].key);
  }, [strategies, pick]);

  const current = useMemo(() => (strategies ?? []).find((s) => s.key === pick) ?? null, [strategies, pick]);
  const running = Boolean(session?.running);
  const acknowledged = Boolean(disclaimer?.acknowledged);
  const mode = active ? (active.account_type === "real" ? "real" : "demo") : null;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-4xl font-bold">Trade</h1>
          <p className="mt-1 text-lg font-semibold text-muted">Run a tested strategy, carefully.</p>
        </div>
        {mode && (
          <Chip className={mode === "real" ? "bg-brand text-on-brand" : "bg-sky text-ink"}>
            {mode === "real" ? "REAL ACCOUNT" : "DEMO ACCOUNT"}
          </Chip>
        )}
      </div>

      <div className="flex gap-3 rounded-3xl bg-honey p-4 text-ink">
        <AlertTriangle className="mt-0.5 size-5 shrink-0" strokeWidth={2.6} />
        <p className="text-sm font-extrabold">
          Educational tool, not financial advice. Every strategy here tested as no better than the house,
          so expect to lose money over time.
        </p>
      </div>

      {error && (
        <p className="rounded-3xl bg-brand/10 px-5 py-3 text-sm font-bold text-brand">{error}</p>
      )}

      {disclaimer === null && !error && <div className="h-40 animate-pulse rounded-[32px] bg-surface" />}

      {disclaimer && !acknowledged && (
        <RiskGate disclaimer={disclaimer} onAccept={acknowledge} busy={busy} />
      )}

      {!active && (
        <p className="rounded-[32px] bg-surface p-6 font-bold text-muted shadow-soft">
          Connect a Deriv account in Settings to trade.
        </p>
      )}

      {acknowledged && strategies && (
        <>
          <StrategyPicker strategies={strategies} pick={pick} onPick={setPick} disabled={running} />
          {current && (
            <StartPanel
              strategy={current}
              active={active}
              mode={mode}
              running={running}
              busy={busy}
              onStart={start}
            />
          )}
        </>
      )}

      {session && <LivePanel session={session} onStop={stop} busy={busy} />}

      {acknowledged && <ResultsPanel stats={stats} />}
      {acknowledged && <TradeList trades={trades} />}
    </div>
  );
}