import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { animate, motion } from "motion/react";
import { Activity, Link2, RefreshCw, TriangleAlert, Target, TrendingUp } from "lucide-react";
import AccountRow from "../components/AccountRow";
import { useAccounts } from "../context/AccountContext";
import { useAuth } from "../context/AuthContext";
import { money } from "../lib/format";
import { useOverview } from "../lib/useOverview";

const group = { hidden: {}, show: { transition: { staggerChildren: 0.09, delayChildren: 0.05 } } };
const rise = {
  hidden: { opacity: 0, y: 26, scale: 0.95 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 300, damping: 22 } },
};

const steps = [
  {
    to: "/markets",
    icon: TrendingUp,
    tone: "bg-lime text-ink",
    title: "Watch live ticks",
    text: "See the synthetic markets move in real time.",
    tag: "Next",
  },
  {
    to: "/analysis",
    icon: Activity,
    tone: "bg-honey text-ink",
    title: "Run the analysis",
    text: "Find out what the numbers really say.",
    tag: "Then",
  },
  {
    to: "/trade",
    icon: Target,
    tone: "bg-berry text-white",
    title: "Trade safely",
    text: "Start on Demo. Go Live only when you are ready.",
    tag: "Last",
  },
];

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function Balance({ value, currency }) {
  const target = value === null || value === undefined ? Number.NaN : Number(value);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (Number.isNaN(target)) return undefined;
    const controls = animate(0, target, { duration: 0.9, ease: "easeOut", onUpdate: setShown });
    return () => controls.stop();
  }, [target]);

  if (Number.isNaN(target)) return <>—</>;
  return <>{money(shown, currency)}</>;
}

function AccountCard({ account }) {
  const real = account.account_type === "real";
  return (
    <div
      className={`relative overflow-hidden rounded-[36px] p-7 shadow-pop ${
        real ? "bg-brand text-on-brand" : "bg-lime text-ink"
      }`}
    >
      <span className="absolute -right-8 -top-8 size-40 rounded-full bg-white/25" />
      <span className="absolute -bottom-10 right-16 size-24 rounded-full bg-honey/80" />
      <p className="relative text-sm font-extrabold uppercase tracking-wide opacity-80">
        {real ? "Live account" : "Demo account"}
      </p>
      <p className="relative mt-2 font-display text-5xl font-bold">
        <Balance value={account.balance} currency={account.currency || "USD"} />
      </p>
      <p className="relative mt-3 font-bold opacity-80">{account.deriv_account_id}</p>
    </div>
  );
}

function Notice({ tone, icon: Icon, title, text, children }) {
  return (
    <div className={`rounded-[36px] p-7 ${tone}`}>
      <span className="grid size-14 place-items-center rounded-full bg-white/30">
        <Icon className="size-7" strokeWidth={2.4} />
      </span>
      <p className="mt-4 font-display text-2xl font-bold">{title}</p>
      <p className="mt-1 font-semibold opacity-90">{text}</p>
      <div className="mt-5">{children}</div>
    </div>
  );
}

const pillButton =
  "inline-flex h-12 items-center gap-2 rounded-full bg-white px-6 font-display font-bold text-ink shadow-soft";

export default function Home() {
  const { user } = useAuth();
  const { active } = useAccounts();
  const { data, loading, reload } = useOverview();
  const first = (user.full_name || user.email).split(" ")[0];
  const accounts = data?.accounts ?? [];
  const current = accounts.find((a) => a.id === active?.id) ?? accounts[0] ?? null;
  const others = accounts.filter((a) => a.id !== current?.id);
  const status = data?.status;

  let top = null;
  if (loading && !data) {
    top = <div className="h-52 animate-pulse rounded-[36px] bg-surface" />;
  } else if (status === "none" || !data) {
    top = (
      <Notice
        tone="bg-brand text-on-brand"
        icon={Link2}
        title="Link your Deriv account"
        text="Connect Demo and Live, then switch with one tap."
      >
        <Link to="/settings" className={pillButton}>
          Link account
        </Link>
      </Notice>
    );
  } else if (status === "expired") {
    top = (
      <Notice
        tone="bg-honey text-ink"
        icon={TriangleAlert}
        title="Reconnect Deriv"
        text="Your Deriv session ended. Link again to keep going."
      >
        <Link to="/settings" className={pillButton}>
          Reconnect
        </Link>
      </Notice>
    );
  } else if (current) {
    top = <AccountCard account={current} />;
  }

  return (
    <motion.div variants={group} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={rise}>
        <h1 className="font-display text-4xl font-bold lg:text-5xl">
          {greeting()}, {first}
        </h1>
        <p className="mt-2 text-lg font-semibold text-muted">{user.tenant.name}</p>
      </motion.div>

      <motion.div variants={rise}>{top}</motion.div>

      {status === "unavailable" && (
        <motion.div
          variants={rise}
          className="flex items-center justify-between gap-4 rounded-3xl bg-surface p-5 shadow-soft"
        >
          <p className="font-bold">Deriv is not responding. Balances are hidden for now.</p>
          <motion.button
            type="button"
            whileTap={{ scale: 0.92 }}
            onClick={reload}
            aria-label="Try again"
            className="grid size-11 shrink-0 place-items-center rounded-full bg-brand text-on-brand"
          >
            <RefreshCw className="size-5" strokeWidth={2.4} />
          </motion.button>
        </motion.div>
      )}

      {others.length > 0 && status !== "expired" && (
        <motion.section variants={rise} className="rounded-[32px] bg-surface p-5 shadow-soft">
          <h2 className="mb-3 font-display text-xl font-bold">Other accounts</h2>
          <div className="space-y-3">
            {others.map((account) => (
              <AccountRow key={account.id} account={account} />
            ))}
          </div>
        </motion.section>
      )}

      <motion.h2 variants={rise} className="pt-2 font-display text-2xl font-bold">
        Coming up
      </motion.h2>
      <div className="grid gap-4 sm:grid-cols-2">
        {steps.map(({ to, icon: Icon, tone, title, text, tag }) => (
          <motion.div key={title} variants={rise}>
            <motion.div whileTap={{ scale: 0.96 }} whileHover={{ y: -3 }}>
              <Link to={to} className="flex items-center gap-4 rounded-[32px] bg-surface p-5 shadow-soft">
                <span className={`grid size-14 shrink-0 place-items-center rounded-full ${tone}`}>
                  <Icon className="size-7" strokeWidth={2.4} />
                </span>
                <span className="min-w-0">
                  <span className="block font-display text-xl font-bold">{title}</span>
                  <span className="mt-0.5 block text-sm font-semibold text-muted">{text}</span>
                  <span className="mt-2 inline-block rounded-full bg-bg px-3 py-1 text-xs font-extrabold text-muted">
                    {tag}
                  </span>
                </span>
              </Link>
            </motion.div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}