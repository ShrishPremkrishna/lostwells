"use client";

import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { CandidateLite } from "@/lib/types";
import { scoreCSS } from "@/lib/colors";
import { fmtInt } from "@/lib/format";

export function RankedList({
  items,
  selectedId,
  onSelect,
  onHover,
}: {
  items: CandidateLite[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const rows = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 76,
    overscan: 8,
  });

  return (
    <div ref={parentRef} className="h-full overflow-y-auto">
      <div style={{ height: rows.getTotalSize(), position: "relative" }}>
        {rows.getVirtualItems().map((vi) => {
          const c = items[vi.index];
          const selected = c.well_id === selectedId;
          const e = c.enrichment || {};
          const pop = e.population_1mi ?? e.population;
          return (
            <button
              key={c.well_id}
              onClick={() => onSelect(c.well_id)}
              onMouseEnter={() => onHover(c.well_id)}
              onMouseLeave={() => onHover(null)}
              className="absolute left-0 top-0 w-full border-b px-4 py-3 text-left"
              style={{
                height: vi.size,
                transform: `translateY(${vi.start}px)`,
                borderColor: "var(--color-base)",
                borderLeft: `3px solid ${scoreCSS(c.score.composite)}`,
                background: selected ? "var(--color-accent-light)" : "transparent",
              }}
            >
              <div className="flex items-center gap-3">
                <span className="tnum w-6 shrink-0 text-xs" style={{ color: "var(--color-mid)" }}>
                  {vi.index + 1}
                </span>
                <span
                  className="tnum w-8 shrink-0 text-right font-display text-lg"
                  style={{ color: "var(--color-text-head)" }}
                >
                  {Math.round(c.score.composite)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium" style={{ color: "var(--color-text-head)" }}>
                      {c.hero?.title ?? `${c.quad_name ?? c.name} quad`}
                    </span>
                    {c.hero?.confirmed && (
                      <span
                        className="shrink-0 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-white"
                        style={{ background: "var(--color-danger)", borderRadius: 4 }}
                      >
                        Confirmed
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 overflow-hidden whitespace-nowrap text-[11px]" style={{ color: "var(--color-mid)" }}>
                    <span className="truncate">{c.county_group?.replace(/_/g, " ") ?? c.state}</span>
                    <span className="shrink-0">·</span>
                    <span className="tnum shrink-0">{fmtInt(pop)} within 1mi</span>
                    {(e.schools_within_1mi ?? 0) > 0 && (
                      <span className="tnum shrink-0" style={{ color: "var(--color-accent-deep)" }}>
                        · {e.schools_within_1mi} schools
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
