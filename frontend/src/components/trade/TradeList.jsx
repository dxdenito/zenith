import { money, toneOf } from "../../lib/tradeFormat";
import { Chip } from "./atoms";

const RESULT_STYLE = {
  won: "bg-lime text-ink",
  lost: "bg-brand text-on-brand",
  open: "bg-honey text-ink",
  unknown: "bg-honey text-ink",
};

function TradeRow({ t }) {
  const delay = t.entry_epoch && t.signal_epoch ? t.entry_epoch - t.signal_epoch : null;
  const contract = `${t.contract_type}${t.barrier ? ` ${t.barrier}` : ""} · ${t.duration}t`;
  return (
    <div className="rounded-3xl bg-bg p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-extrabold">{contract}</p>
          <p className="truncate text-xs font-bold text-muted">
            {new Date(t.created_at).toLocaleTimeString()} · {t.symbol} · {t.mode} · stake {t.stake}
            {t.step > 1 ? ` · step ${t.step}` : ""}
            {t.payout ? ` · pays ${t.payout.toFixed(2)}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`font-display text-lg font-bold ${toneOf(t.profit)}`}>{money(t.profit)}</span>
          <Chip className={RESULT_STYLE[t.status] ?? "bg-bg text-text"}>
            {t.status === "unknown" ? "check" : t.status}
          </Chip>
        </div>
      </div>
      {delay != null && (
        <p className="mt-1 text-xs font-bold text-muted">
          Signal to entry tick: {delay}s (signal {t.signal_epoch}, entry {t.entry_epoch})
        </p>
      )}
      {t.error && <p className="mt-1 text-xs font-bold text-brand">{t.error}</p>}
    </div>
  );
}

export default function TradeList({ trades }) {
  return (
    <section className="space-y-3">
      <h2 className="font-display text-2xl font-bold">Trades</h2>
      {trades.length === 0 && (
        <p className="rounded-[32px] bg-surface p-6 font-bold text-muted shadow-soft">
          No trades on this account yet.
        </p>
      )}
      {trades.map((t) => (
        <TradeRow key={t.id} t={t} />
      ))}
    </section>
  );
}