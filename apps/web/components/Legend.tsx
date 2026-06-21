"use client";

import { DISCOVERED, DOCUMENTED } from "@/lib/colors";

const rgb = (c: [number, number, number], a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

export function Legend({ showDocumented }: { showDocumented: boolean }) {
  return (
    <div
      className="pointer-events-none absolute bottom-5 right-5 z-20 border p-3 text-[11px]"
      style={{ background: "var(--color-surface-1)", borderColor: "var(--color-base)" }}
    >
      <div className="mb-1.5 uppercase tracking-[0.08em]" style={{ color: "var(--color-mid)" }}>
        Map legend
      </div>
      <div className="space-y-1">
        <Row color={rgb(DISCOVERED)} label="Lost well we discovered (U-Net)" />
        {showDocumented && <Row color={rgb(DOCUMENTED, 0.7)} label="Documented well (117,672)" />}
      </div>
    </div>
  );
}

function Row({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2" style={{ color: "var(--color-text-body)" }}>
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </div>
  );
}
