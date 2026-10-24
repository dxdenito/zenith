import { Zap } from "lucide-react";

export default function Brand({ inverted = false }) {
  return (
    <div className="flex items-center gap-3 font-display text-2xl font-bold">
      <span
        className={`grid size-11 place-items-center rounded-full ${
          inverted ? "bg-white text-brand" : "bg-brand text-on-brand"
        }`}
      >
        <Zap className="size-6" strokeWidth={2.4} fill="currentColor" />
      </span>
      Zenith
    </div>
  );
}
