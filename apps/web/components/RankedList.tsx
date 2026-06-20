"use client";

import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { Candidate } from "@/lib/types";
import { scoreCSS } from "@/lib/colors";
import { fmtInt, fmtMiles } from "@/lib/format";

export function RankedList({
  items,
  selectedId,
  onSelect,
  onHover,
}: {
  items: Candidate[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const rows = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 78,
    overscan: 8,
  });

  return (
    <div ref={parentRef} className="h-full overflow-y-auto">
      <div style={{ height: rows.getTotalSize(), position: "relative" }}>
        {rows.getVirtualItems().map((vi) => {
          const c = items[vi.index];
          const selected = c.well_id === selectedId;
          const e = c.enrichment || {};
          return (
            <button
              key={c.well_id}
              onClick={() => onSelect(c.well_id)}
              onMouseEnter={() => onHover(c.well_id)}
              onMouseLeave={() => onHover(null)}
              className={`absolute left-0 top-0 w-full border-b border-white/[0.05] px-4 py-3 text-left transition-colors ${
                selected ? "bg-ember/[0.08]" : "hover:bg-white/[0.03]"
              }`}
              style={{ height: vi.size, transform: `translateY(${vi.start}px)` }}
            >
              <div className="flex items-center gap-3">
                <span className="tnum w-7 shrink-0 text-xs text-ink-400">
                  {c.rank}
                </span>
                <span
                  className="tnum flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-semibold text-ink-950"
                  style={{ background: scoreCSS(c.score.composite) }}
                >
                  {Math.round(c.score.composite)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-ink-100">
                      {c.hero?.title ?? `${c.quad_name ?? c.name}`}
                    </span>
                    {c.hero?.confirmed && (
                      <span className="shrink-0 rounded bg-danger/20 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-danger">
                        Confirmed
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-[11px] text-ink-400">
                    <span>{c.hero?.place ?? `${c.county_group?.replace(/_/g, " ") ?? c.state}`}</span>
                    <span className="text-ink-600">·</span>
                    <span className="tnum">{fmtInt(e.population)} nearby</span>
                    {(e.schools_within_1mi ?? 0) > 0 && (
                      <>
                        <span className="text-ink-600">·</span>
                        <span className="tnum text-ember-soft">🏫 {e.schools_within_1mi}</span>
                      </>
                    )}
                  </div>
                </div>
                {e.nearest_school_m != null && (
                  <span className="tnum shrink-0 text-[10px] text-ink-500">
                    {fmtMiles(e.nearest_school_m)}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
