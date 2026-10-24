import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { CircleCheck, Link2, LogOut, Moon, RefreshCw, Sun } from "lucide-react";
import AccountRow from "../components/AccountRow";
import { Button } from "../components/ui";
import { useAccounts } from "../context/AccountContext";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { api } from "../lib/api";
import { useOverview } from "../lib/useOverview";

const modes = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
];

const notes = {
  linked: { text: "Your Deriv account is linked.", tone: "bg-lime text-ink" },
  denied: { text: "The link was cancelled. You can try again anytime.", tone: "bg-honey text-ink" },
  expired: { text: "That took too long. Please try again.", tone: "bg-honey text-ink" },
  invalid: { text: "The link could not be verified. Please try again.", tone: "bg-brand/10 text-brand" },
  failed: { text: "Linking failed. Please try again.", tone: "bg-brand/10 text-brand" },
};

const subtitles = {
  none: "Link Demo and Live in one step.",
  active: "Linked. Demo and Live are ready.",
  expired: "Your session ended. Link again to continue.",
  unavailable: "Linked, but Deriv is not responding right now.",
};

export default function Settings() {
  const { user, logout } = useAuth();
  const { active } = useAccounts();
  const { theme, setTheme } = useTheme();
  const { data, loading, error: loadError, reload } = useOverview();
  const [params, setParams] = useSearchParams();
  const [flash] = useState(() => params.get("deriv"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const name = user.full_name || user.email;
  const note = flash ? notes[flash] : null;
  const status = data?.status ?? "none";
  const linked = status === "active" || status === "unavailable";

  useEffect(() => {
    if (params.has("deriv")) setParams({}, { replace: true });
  }, []);

  async function connect() {
    setBusy(true);
    setError("");
    try {
      const { authorize_url } = await api.connectDeriv();
      window.location.assign(authorize_url);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-4xl font-bold">Settings</h1>

      {note && <p className={`rounded-3xl px-5 py-4 font-extrabold ${note.tone}`}>{note.text}</p>}

      <section className="flex items-center gap-4 rounded-[32px] bg-surface p-5 shadow-soft">
        <span className="grid size-16 shrink-0 place-items-center rounded-full bg-deep font-display text-2xl font-bold text-on-deep">
          {name.charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0">
          <p className="truncate font-display text-xl font-bold">{name}</p>
          <p className="truncate font-semibold text-muted">{user.email}</p>
          <p className="mt-1 truncate text-sm font-bold text-muted">{user.tenant.name}</p>
        </div>
      </section>

      <section className="rounded-[32px] bg-surface p-5 shadow-soft">
        <div className="flex items-center gap-3">
          <span className="grid size-12 shrink-0 place-items-center rounded-full bg-brand text-on-brand">
            <Link2 className="size-6" strokeWidth={2.4} />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-xl font-bold">Deriv account</h2>
            <p className="text-sm font-semibold text-muted">
              {loading && !data ? "Checking your link…" : subtitles[status]}
            </p>
          </div>
          {linked && (
            <span className="flex items-center gap-1 rounded-full bg-lime px-3 py-1.5 text-xs font-extrabold text-ink">
              <CircleCheck className="size-4" strokeWidth={2.8} />
              Linked
            </span>
          )}
        </div>

        {(error || loadError) && (
          <p className="mt-4 rounded-3xl bg-brand/10 px-5 py-3 text-sm font-bold text-brand">
            {error || loadError}
          </p>
        )}

        {loading && !data && <div className="mt-4 h-20 animate-pulse rounded-3xl bg-bg" />}

        {data && status !== "none" && data.accounts.length > 0 && (
          <div className="mt-4 space-y-3">
            {data.accounts.map((account) => (
              <AccountRow key={account.id} account={account} active={account.id === active?.id} />
            ))}
          </div>
        )}

        {!(loading && !data) && (
          <div className="mt-4 space-y-3">
            {linked ? (
              <motion.button
                type="button"
                whileTap={{ scale: 0.96 }}
                onClick={connect}
                disabled={busy}
                className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-bg font-display text-base font-bold disabled:opacity-70"
              >
                <RefreshCw className="size-5" strokeWidth={2.4} />
                Link again
              </motion.button>
            ) : (
              <Button type="button" onClick={connect} loading={busy}>
                {status === "expired" ? "Reconnect Deriv" : "Link Deriv account"}
              </Button>
            )}
            {loadError && (
              <motion.button
                type="button"
                whileTap={{ scale: 0.96 }}
                onClick={reload}
                className="flex h-12 w-full items-center justify-center rounded-full bg-bg font-display text-base font-bold"
              >
                Try again
              </motion.button>
            )}
          </div>
        )}
      </section>

      <section className="rounded-[32px] bg-surface p-5 shadow-soft">
        <h2 className="mb-4 font-display text-xl font-bold">Look and feel</h2>
        <div className="flex rounded-full bg-bg p-1.5">
          {modes.map(({ value, label, icon: Icon }) => {
            const selected = theme === value;
            return (
              <button
                key={value}
                type="button"
                onClick={() => setTheme(value)}
                className="relative flex-1 rounded-full py-3"
              >
                {selected && (
                  <motion.span
                    layoutId="theme-pill"
                    transition={{ type: "spring", stiffness: 480, damping: 34 }}
                    className="absolute inset-0 rounded-full bg-brand shadow-pop"
                  />
                )}
                <span
                  className={`relative flex items-center justify-center gap-2 font-extrabold ${
                    selected ? "text-on-brand" : "text-muted"
                  }`}
                >
                  <Icon className="size-5" strokeWidth={2.4} />
                  {label}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <motion.button
        type="button"
        onClick={logout}
        whileTap={{ scale: 0.95 }}
        className="flex h-14 w-full items-center justify-center gap-2 rounded-full bg-surface font-display text-lg font-bold shadow-soft"
      >
        <LogOut className="size-5" strokeWidth={2.4} />
        Sign out
      </motion.button>
    </div>
  );
}