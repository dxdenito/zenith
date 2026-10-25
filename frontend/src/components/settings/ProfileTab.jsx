import { motion } from "motion/react";
import { LogOut } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-3xl bg-bg px-5 py-3.5">
      <span className="text-sm font-extrabold text-muted">{label}</span>
      <span className="min-w-0 truncate font-bold">{value}</span>
    </div>
  );
}

export default function ProfileTab() {
  const { user, logout } = useAuth();
  const name = user.full_name || user.email;

  return (
    <div className="space-y-6">
      <section className="flex items-center gap-4 rounded-[32px] bg-surface p-5 shadow-soft">
        <span className="grid size-16 shrink-0 place-items-center rounded-full bg-deep font-display text-2xl font-bold text-on-deep">
          {name.charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0">
          <p className="truncate font-display text-xl font-bold">{name}</p>
          <p className="truncate font-semibold text-muted">{user.email}</p>
        </div>
      </section>

      <section className="rounded-[32px] bg-surface p-5 shadow-soft">
        <h2 className="mb-4 font-display text-xl font-bold">Details</h2>
        <div className="space-y-2">
          <Row label="Name" value={user.full_name || "—"} />
          <Row label="Email" value={user.email} />
          <Row label="Workspace" value={user.tenant.name} />
          <Row label="Role" value={user.role} />
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