import { motion } from "motion/react";
import { Square } from "lucide-react";
import { money, toneOf } from "../../lib/tradeFormat";
import { Chip, Tile } from "./atoms";

const STATUS_STYLE = {
  starting: "bg-honey text-ink",
  running: "bg-lime text-ink",
  halted: "bg-brand text-on-brand",
  stopped: "bg-bg text-text",
};

export default function LivePanel({ session, onStop, busy }) {
  const age = session.last_tick
    ? Math.max(0, Math.round(Date.now() / 1000 - session.last_tick))
    : null;

  return (
    <section className="space-y-4 rounded-[32px] bg-surface p-5 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-display text-xl font-bold">{session.strategy_name}</p>
          <p className="text-xs font-extrabold text-muted">
            {session.symbol} · stake {session.stake} · {session.mode.toUpperCase()}
          </p>
        </div>
        <Chip className={STATUS_STYLE[session.status] ?? "bg-bg text-text"}>{session.status}</Chip>
      </div>
      <p className="rounded-3xl bg-bg p-4 text-sm font-bold">{session.message}</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile label="Signals seen" value={session.signals} />
        <Tile label="Trades settled" value={session.trades} />
        <Tile label="Wins / losses" value={`${session.wins} / ${session.losses}`} />
        <Tile label="Session result" value={money(session.profit)} valueClass={toneOf(session.profit)} />
        <Tile label="Losses in a row" value={session.streak} />
        {session.martingale && (
          <>
            <Tile label="Martingale step" value={`${session.step} of ${session.max_steps}`} />
            <Tile label="Next stake" value={Number(session.stake).toFixed(2)} />
            <Tile label="Cap hits" value={session.cap_hits} />
          </>
        )}
        {session.session_target != null && (
          <>
            <Tile
              label="This session"
              value={`${money(session.session_profit)} of +${Number(session.session_target).toFixed(2)}`}
              valueClass={toneOf(session.session_profit)}
            />
            <Tile label="Targets hit / sessions" value={`${session.targets_hit} / ${session.sessions_done}`} />
          </>
        )}
        <Tile
          label="Last tick"
          value={age == null ? "—" : `${age}s ago`}
          valueClass={age != null && age > 30 ? "text-brand" : ""}
        />
      </div>
      {session.settling && (
        <p className="text-sm font-bold text-muted">A contract is open. Waiting for its result.</p>
      )}
      {session.session_target != null && session.running && (
        <p className="text-sm font-bold text-muted">
          {session.rest_until
            ? `Resting until ${new Date(session.rest_until * 1000).toLocaleTimeString()}.`
            : `Session window ends at ${new Date(session.window_end * 1000).toLocaleTimeString()}.`}
        </p>
      )}
      {session.running && (
        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          disabled={busy}
          onClick={onStop}
          className="flex h-12 items-center gap-2 rounded-full bg-text px-6 font-extrabold text-bg disabled:opacity-60"
        >
          <Square className="size-4" strokeWidth={3} />
          {busy ? "Stopping after the current trade…" : "Stop"}
        </motion.button>
      )}
    </section>
  );
}