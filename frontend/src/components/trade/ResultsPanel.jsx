import { money, pct, toneOf } from "../../lib/tradeFormat";
import { Tile } from "./atoms";

export default function ResultsPanel({ stats }) {
  if (!stats) return null;
  return (
    <section className="rounded-[32px] bg-surface p-5 shadow-soft">
      <h2 className="font-display text-xl font-bold">Results on this account</h2>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile label="Settled trades" value={stats.trades} />
        <Tile label="Win rate" value={pct(stats.win_rate)} />
        <Tile label="Needed to break even" value={pct(stats.breakeven)} />
        <Tile label="Actual result" value={money(stats.profit)} valueClass={toneOf(stats.profit)} />
        <Tile
          label="Expected with no edge"
          value={money(stats.expected_profit)}
          valueClass={toneOf(stats.expected_profit)}
        />
      </div>
      <p className="mt-3 text-xs font-bold text-muted">
        "Expected with no edge" is what these trades return on average if every call has exactly the true
        odds. It is negative because the house margin comes out of every trade.
      </p>
    </section>
  );
}