import { useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown, Link2, ShieldAlert } from "lucide-react";
import { useAccounts } from "../context/AccountContext";

const tone = { demo: "bg-lime text-ink", real: "bg-brand text-on-brand" };
const names = { demo: "Demo", real: "Live" };

export default function AccountSwitcher() {
  const { active, accounts, loading, switchTo } = useAccounts();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (loading) return <div className="h-11 w-24 animate-pulse rounded-full bg-surface" />;

  if (!active) {
    return (
      <motion.button
        type="button"
        whileTap={{ scale: 0.92 }}
        onClick={() => navigate("/settings")}
        className="flex h-11 items-center gap-2 rounded-full bg-surface px-4 text-sm font-extrabold shadow-soft"
      >
        <Link2 className="size-4" strokeWidth={2.6} />
        Link account
      </motion.button>
    );
  }

  function close() {
    setOpen(false);
    setPending(null);
    setError("");
  }

  async function change(account) {
    setBusy(true);
    setError("");
    try {
      await switchTo(account.id);
      close();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function choose(account) {
    if (account.id === active.id) {
      close();
    } else if (account.account_type === "real") {
      setPending(account);
    } else {
      change(account);
    }
  }

  return (
    <>
      <motion.button
        type="button"
        whileTap={{ scale: 0.92 }}
        onClick={() => setOpen(true)}
        className={`flex h-11 items-center gap-2 rounded-full px-4 text-sm font-extrabold shadow-soft ${tone[active.account_type]}`}
      >
        {active.account_type === "real" && (
          <motion.span
            animate={{ opacity: [1, 0.35, 1] }}
            transition={{ duration: 1.6, repeat: Infinity }}
            className="size-2 rounded-full bg-current"
          />
        )}
        {names[active.account_type]}
        <ChevronDown className="size-4" strokeWidth={2.8} />
      </motion.button>

      {createPortal(
        <AnimatePresence>
          {open && (
            <>
              <motion.div
                key="backdrop"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={close}
                className="fixed inset-0 z-50 bg-black/50"
              />
              <div
                key="wrap"
                className="pointer-events-none fixed inset-0 z-50 flex items-end justify-center lg:items-center"
              >
                <motion.div
                  initial={{ y: 80, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: 80, opacity: 0 }}
                  transition={{ type: "spring", stiffness: 320, damping: 30 }}
                  className="pointer-events-auto w-full rounded-t-[36px] bg-surface p-6 text-text shadow-lift lg:max-w-md lg:rounded-[36px]"
                  style={{ paddingBottom: "calc(1.5rem + env(safe-area-inset-bottom, 0px))" }}
                >
                  {pending ? (
                    <div className="text-center">
                      <span className="mx-auto grid size-16 place-items-center rounded-full bg-brand/10 text-brand">
                        <ShieldAlert className="size-8" strokeWidth={2.4} />
                      </span>
                      <h2 className="mt-4 font-display text-2xl font-bold">Switch to Live?</h2>
                      <p className="mt-2 font-semibold text-muted">
                        Live uses real money. Trades placed there are real.
                      </p>
                      {error && <p className="mt-3 text-sm font-bold text-brand">{error}</p>}
                      <div className="mt-6 grid gap-3">
                        <motion.button
                          type="button"
                          whileTap={{ scale: 0.96 }}
                          disabled={busy}
                          onClick={() => change(pending)}
                          className="h-14 rounded-full bg-brand font-display text-lg font-bold text-on-brand shadow-pop disabled:opacity-70"
                        >
                          Yes, go Live
                        </motion.button>
                        <motion.button
                          type="button"
                          whileTap={{ scale: 0.96 }}
                          onClick={() => setPending(null)}
                          className="h-14 rounded-full bg-bg font-display text-lg font-bold"
                        >
                          Stay on Demo
                        </motion.button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <h2 className="font-display text-2xl font-bold">Choose account</h2>
                      <p className="mt-1 font-semibold text-muted">Demo is for practice. Live is real money.</p>
                      {error && <p className="mt-3 text-sm font-bold text-brand">{error}</p>}
                      <div className="mt-5 space-y-3">
                        {accounts.map((account) => {
                          const selected = account.id === active.id;
                          return (
                            <motion.button
                              key={account.id}
                              type="button"
                              whileTap={{ scale: 0.97 }}
                              disabled={busy}
                              onClick={() => choose(account)}
                              className={`flex w-full items-center gap-4 rounded-3xl bg-bg p-4 text-left ring-2 ${
                                selected ? "ring-brand" : "ring-transparent"
                              }`}
                            >
                              <span
                                className={`grid h-11 min-w-16 place-items-center rounded-full px-3 text-sm font-extrabold ${tone[account.account_type]}`}
                              >
                                {names[account.account_type]}
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className="block truncate font-extrabold">
                                  {account.deriv_account_id}
                                </span>
                                <span className="block text-sm font-semibold text-muted">
                                  {account.currency || "USD"}
                                </span>
                              </span>
                              {selected && <Check className="size-6 text-brand" strokeWidth={3} />}
                            </motion.button>
                          );
                        })}
                      </div>
                    </>
                  )}
                </motion.div>
              </div>
            </>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
}