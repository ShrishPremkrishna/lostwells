"use client";

import { GROUP_COLORS } from "@/lib/colors";
import { GROUP_LABELS } from "@/lib/types";

const ORDER = ["human_exposure", "equity", "methane", "fundability"];

export function ScoreBar({
  groups,
  composite,
  height = 8,
  showLegend = false,
}: {
  groups: Record<string, number>;
  composite: number;
  height?: number;
  showLegend?: boolean;
}) {
  return (
    <div>
      <div
        className="flex w-full overflow-hidden rounded-full bg-ink-800"
        style={{ height }}
      >
        {ORDER.map((g) => {
          const w = groups[g] ?? 0;
          if (w <= 0) return null;
          return (
            <div
              key={g}
              style={{ width: `${w}%`, background: GROUP_COLORS[g] }}
              title={`${GROUP_LABELS[g]}: ${w.toFixed(1)} pts`}
              className="h-full transition-all"
            />
          );
        })}
      </div>
      {showLegend && (
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {ORDER.map((g) => (
            <span key={g} className="flex items-center gap-1.5 text-[10px] text-ink-300">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: GROUP_COLORS[g] }}
              />
              {GROUP_LABELS[g]}
              <span className="tnum text-ink-200">{(groups[g] ?? 0).toFixed(0)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
