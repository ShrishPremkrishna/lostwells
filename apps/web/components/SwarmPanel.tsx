"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Candidate, Dossier } from "@/lib/types";
import { scoreCSS } from "@/lib/colors";

const STAGES = [
  "queued",
  "searching operator history",
  "checking bankruptcy & shell transfers",
  "scanning local news",
  "scoring dossier",
  "done",
] as const;

interface AgentState {
  stage: number;
  done: boolean;
}

export function SwarmPanel({
  open,
  candidates,
  dossiers,
  onClose,
  onSelect,
}: {
  open: boolean;
  candidates: Candidate[];
  dossiers: Record<string, Dossier>;
  onClose: () => void;
  onSelect: (id: string) => void;
}) {
  // the swarm visualizes the wells with cached dossiers, else the top-ranked.
  const cohort = useMemo(() => {
    const withDossier = candidates.filter((c) => dossiers[c.well_id]?.narrative);
    const base = withDossier.length ? withDossier : candidates.slice(0, 12);
    return base.slice(0, 12);
  }, [candidates, dossiers]);

  const [agents, setAgents] = useState<Record<string, AgentState>>({});
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!open) return;
    // seed: cached dossiers start "done"
    const seed: Record<string, AgentState> = {};
    cohort.forEach((c) => {
      seed[c.well_id] = dossiers[c.well_id]?.narrative
        ? { stage: STAGES.length - 1, done: true }
        : { stage: 0, done: false };
    });
    setAgents(seed);
  }, [open, cohort, dossiers]);

  // animated "replay" of the investigation for the visualization
  function replay() {
    setRunning(true);
    const reset: Record<string, AgentState> = {};
    cohort.forEach((c) => (reset[c.well_id] = { stage: 0, done: false }));
    setAgents(reset);
    cohort.forEach((c, i) => {
      const steps = STAGES.length - 1;
      for (let s = 1; s <= steps; s++) {
        setTimeout(() => {
          setAgents((prev) => ({
            ...prev,
            [c.well_id]: { stage: s, done: s === steps },
          }));
          if (i === cohort.length - 1 && s === steps) setRunning(false);
        }, 350 * s + i * 160);
      }
    });
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 30, opacity: 0 }}
          transition={{ type: "spring", stiffness: 200, damping: 26 }}
          className="absolute bottom-6 left-1/2 z-30 w-[640px] max-w-[calc(100vw-440px)] -translate-x-1/2 rounded-2xl border border-white/10 bg-ink-900/95 p-4 shadow-panel backdrop-blur-md"
          style={{ left: "calc(50% + 190px)" }}
        >
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-display text-sm text-paper">Claude investigator swarm</span>
                <span className="rounded bg-ember/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-ember-soft">
                  LangGraph · map-reduce
                </span>
              </div>
              <p className="mt-0.5 text-[10px] text-ink-400">
                One isolated-context agent per well: open-ended web search for operator history,
                bankruptcy, and local news → a structured dossier.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={replay}
                disabled={running}
                className="rounded-lg border border-ember/40 bg-ember/10 px-3 py-1.5 text-[11px] font-medium text-ember-soft hover:bg-ember/20 disabled:opacity-50"
              >
                {running ? "Running…" : "▶ Replay swarm"}
              </button>
              <button
                onClick={onClose}
                className="rounded-lg border border-white/10 px-2 py-1.5 text-[11px] text-ink-400 hover:text-ink-100"
              >
                ✕
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {cohort.map((c) => {
              const a = agents[c.well_id] ?? { stage: 0, done: false };
              const stage = STAGES[a.stage];
              return (
                <button
                  key={c.well_id}
                  onClick={() => onSelect(c.well_id)}
                  className="group rounded-lg border border-white/[0.07] bg-ink-850/70 p-2.5 text-left hover:border-ember/30"
                >
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2.5 w-2.5">
                      {!a.done && (
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ember opacity-75" />
                      )}
                      <span
                        className="relative inline-flex h-2.5 w-2.5 rounded-full"
                        style={{ background: a.done ? scoreCSS(c.score.composite) : "#ff7a18" }}
                      />
                    </span>
                    <span className="truncate text-[11px] font-medium text-ink-100">
                      {c.quad_name ?? c.name}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-ink-800">
                    <div
                      className="h-full rounded-full bg-ember transition-all duration-300"
                      style={{ width: `${(a.stage / (STAGES.length - 1)) * 100}%` }}
                    />
                  </div>
                  <div className="mt-1 truncate text-[9.5px] text-ink-400">{stage}</div>
                </button>
              );
            })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
