"use client";

import { motion, AnimatePresence } from "framer-motion";
import { fmtInt } from "@/lib/format";

export function IntroOverlay({
  open,
  onClose,
  documentedCount,
  candidateCount,
}: {
  open: boolean;
  onClose: () => void;
  documentedCount: number;
  candidateCount: number;
}) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 z-40 flex items-center justify-center bg-ink-950/80 backdrop-blur-sm"
        >
          <motion.div
            initial={{ y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 12, opacity: 0 }}
            transition={{ type: "spring", stiffness: 120, damping: 18 }}
            className="mx-4 max-w-2xl rounded-2xl border border-white/10 bg-ink-900/95 p-8 shadow-panel"
          >
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-ember-soft">
              An investigative map
            </div>
            <h1 className="font-display mt-2 text-4xl leading-[1.05] text-paper">
              17.6 million Americans live within a mile of an oil or gas well.
            </h1>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-200">
              For <span className="text-paper">undocumented orphaned wells</span>, that exposure is
              literally uncounted — wells under a school gym, six feet from a family&apos;s drinking
              water. We extend LBNL&apos;s U-Net detector across historical USGS topo maps, layer{" "}
              <span className="tnum text-paper">{fmtInt(candidateCount)}</span> candidate
              undocumented wells over{" "}
              <span className="tnum text-paper">{fmtInt(documentedCount)}</span> documented ones,
              send a Claude agent swarm to investigate each, and rank them by human impact under the
              finite <span className="text-paper">$4.7B</span> federal plugging budget.
            </p>
            <div className="mt-6 flex items-center gap-3">
              <button
                onClick={onClose}
                className="rounded-lg bg-ember px-5 py-2.5 text-sm font-semibold text-ink-950 shadow-glow transition-transform hover:scale-[1.02]"
              >
                Explore the map →
              </button>
              <span className="text-[11px] text-ink-500">
                Methane figures are modeled estimates. Data sources disclosed throughout.
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
