import { Check } from "lucide-react";
import { money } from "../lib/format";

const tone = { demo: "bg-lime text-ink", real: "bg-brand text-on-brand" };
const names = { demo: "Demo", real: "Live" };

export default function AccountRow({ account, active = false }) {
  return (
    <div
      className={`flex items-center gap-4 rounded-3xl bg-bg p-4 ring-2 ${
        active ? "ring-brand" : "ring-transparent"
      }`}
    >
      <span
        className={`grid h-11 min-w-16 place-items-center rounded-full px-3 text-sm font-extrabold ${tone[account.account_type]}`}
      >
        {names[account.account_type]}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-extrabold">{account.deriv_account_id}</p>
        <p className="text-sm font-semibold text-muted">
          {money(account.balance, account.currency || "USD")}
        </p>
      </div>
      {active && <Check className="size-6 text-brand" strokeWidth={3} />}
    </div>
  );
}