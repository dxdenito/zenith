import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Eye, EyeOff, LoaderCircle } from "lucide-react";

export function Button({ loading = false, disabled, children, className = "", ...props }) {
  return (
    <motion.button
      whileTap={{ scale: 0.95 }}
      whileHover={{ scale: 1.02 }}
      transition={{ type: "spring", stiffness: 500, damping: 24 }}
      disabled={loading || disabled}
      className={`flex h-14 w-full items-center justify-center gap-2 rounded-full bg-brand px-6 font-display text-lg font-bold text-on-brand shadow-pop disabled:opacity-70 ${className}`}
      {...props}
    >
      <AnimatePresence mode="wait" initial={false}>
        {loading ? (
          <motion.span
            key="loading"
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.5 }}
            transition={{ duration: 0.15 }}
          >
            <LoaderCircle className="size-6 animate-spin" strokeWidth={2.6} />
          </motion.span>
        ) : (
          <motion.span
            key="label"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.15 }}
          >
            {children}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}

export function Field({ icon: Icon, label, type = "text", ...props }) {
  const [shown, setShown] = useState(false);
  const isPassword = type === "password";

  return (
    <label className="block">
      <span className="mb-2 block px-2 text-sm font-extrabold text-muted">{label}</span>
      <span className="flex h-14 items-center gap-3 rounded-full bg-bg px-5 ring-2 ring-transparent transition focus-within:ring-brand">
        <Icon className="size-5 shrink-0 text-muted" strokeWidth={2.4} />
        <input
          type={isPassword && shown ? "text" : type}
          className="h-full min-w-0 flex-1 bg-transparent text-base font-bold outline-none placeholder:font-semibold placeholder:text-muted/60"
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShown((s) => !s)}
            aria-label={shown ? "Hide password" : "Show password"}
            className="text-muted"
          >
            {shown ? (
              <EyeOff className="size-5" strokeWidth={2.4} />
            ) : (
              <Eye className="size-5" strokeWidth={2.4} />
            )}
          </button>
        )}
      </span>
    </label>
  );
}

export function ErrorNote({ message }) {
  return (
    <AnimatePresence initial={false}>
      {message && (
        <motion.div
          key={message}
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ type: "spring", stiffness: 400, damping: 32 }}
          className="overflow-hidden"
        >
          <p className="rounded-3xl bg-brand/10 px-5 py-3 text-sm font-bold text-brand">{message}</p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
