import type { LLMStatus, Tier } from "@/lib/types";

interface Props {
  status: LLMStatus;
  tier: Tier;
  onChange: (tier: Tier) => void;
}

export function TierPicker({ status, tier, onChange }: Props) {
  return (
    <div className="flex items-center gap-2">
      <div
        role="radiogroup"
        aria-label="AI tier"
        className="flex overflow-hidden rounded-md border border-border text-xs"
      >
        {status.tiers.map((t) => (
          <button
            key={t.tier}
            type="button"
            role="radio"
            aria-checked={tier === t.tier}
            title={`${t.description} (${t.model})`}
            onClick={() => onChange(t.tier)}
            className={`px-2 py-0.5 ${tier === t.tier ? "bg-accent text-white" : "hover:bg-selected"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}
