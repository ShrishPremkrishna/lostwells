"use client";

import { motion, AnimatePresence } from "framer-motion";
import { fmtInt } from "@/lib/format";
import type { Meta } from "@/lib/types";

export function IntroOverlay({
  open,
  onClose,
  meta,
}: {
  open: boolean;
  onClose: () => void;
  meta: Meta | null;
}) {
  const unet = meta?.discovery?.by_source?.unet_appalachia?.candidates ?? 36919;
  const offRecord = meta?.discovery?.gt_100m ?? 38095;
  const documented = meta?.documented_count ?? 117672;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 z-40 flex items-center justify-center p-4"
          style={{ background: "rgba(13,13,13,0.55)" }}
        >
          <motion.div
            initial={{ y: 16, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 8, opacity: 0 }}
            transition={{ type: "spring", stiffness: 140, damping: 20 }}
            className="max-w-2xl border p-8"
            style={{ background: "var(--color-surface-1)", borderColor: "var(--color-base)" }}
          >
            <div className="text-[11px] uppercase tracking-[0.2em]" style={{ color: "var(--color-accent)" }}>
              An investigative field survey
            </div>
            <h1 className="mt-2 font-display text-4xl leading-[1.08]" style={{ color: "var(--color-text-head)" }}>
              We found {fmtInt(unet)} oil &amp; gas wells nobody had on record.
            </h1>
            <p className="mt-4 text-[15px] leading-relaxed" style={{ color: "var(--color-text-body)" }}>
              About <strong>80%</strong> of America&apos;s undocumented orphaned wells are
              in Appalachia — so we ran a U-Net over historical USGS topographic maps and,
              in a single overnight run across four states, surfaced{" "}
              <span className="tnum" style={{ color: "var(--color-text-head)" }}>{fmtInt(unet)}</span>{" "}
              candidate wells. <span className="tnum" style={{ color: "var(--color-text-head)" }}>{fmtInt(offRecord)}</span>{" "}
              sit more than 100&nbsp;m from any of the {fmtInt(documented)} documented wells —
              genuinely off the record. We rank them by who lives on top of them, and map a
              path to plug them.
            </p>
            <div className="mt-6 flex items-center gap-4">
              <button
                onClick={onClose}
                className="px-5 py-2.5 text-[13px] font-semibold uppercase tracking-[0.06em] text-white transition-colors"
                style={{ background: "var(--color-accent)" }}
              >
                Explore the map →
              </button>
              <span className="text-[11px]" style={{ color: "var(--color-mid)" }}>
                Detections are candidates, not confirmed wells. Methane is a modeled estimate.
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
