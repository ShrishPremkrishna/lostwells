"use client";

import { scoreCSS, TEAL, DANGER } from "@/lib/colors";

export function Legend({ showDocumented }: { showDocumented: boolean }) {
  return (
    <div className="pointer-events-none absolute bottom-6 left-5 z-20 rounded-xl border border-white/10 bg-ink-900/85 p-3 text-[11px] backdrop-blur">
      <div className="mb-1.5 font-semibold uppercase tracking-wider text-ink-400">Impact score</div>
      <div className="flex items-center gap-2">
        <div
          className="h-2 w-32 rounded-full"
          style={{
            background: `linear-gradient(90deg, ${scoreCSS(30)}, ${scoreCSS(55)}, ${scoreCSS(72)}, ${scoreCSS(95)})`,
          }}
        />
      </div>
      <div className="tnum mt-0.5 flex w-32 justify-between text-[9px] text-ink-500">
        <span>low</span>
        <span>high</span>
      </div>
      <div className="mt-2.5 space-y-1">
        <Row color={`rgb(${DANGER.join(",")})`} label="Confirmed-exposure hero wells" />
        <Row color="rgb(255,122,24)" label="Candidate UOW (U-Net)" />
        {showDocumented && (
          <Row color={`rgba(${TEAL.join(",")},0.5)`} label="Documented well (117,672)" />
        )}
      </div>
    </div>
  );
}

function Row({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2 text-ink-300">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </div>
  );
}
