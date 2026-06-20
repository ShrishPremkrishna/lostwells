"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence, motion } from "framer-motion";
import type { FocusTarget } from "@/components/MapView";
import { RankedList } from "@/components/RankedList";
import { DossierPanel } from "@/components/DossierPanel";
import { Legend } from "@/components/Legend";
import { IntroOverlay } from "@/components/IntroOverlay";
import { SwarmPanel } from "@/components/SwarmPanel";
import type { Candidate, DocumentedWells, Dossier, Meta } from "@/lib/types";
import { loadCandidates, loadDocumented, loadDossiers, loadHeroes, loadMeta } from "@/lib/data";
import { fmtInt } from "@/lib/format";
import { scoreCSS } from "@/lib/colors";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

type SortKey = "impact" | "population" | "schools";

export default function Page() {
  const [documented, setDocumented] = useState<DocumentedWells | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [heroes, setHeroes] = useState<Candidate[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [dossiers, setDossiers] = useState<Record<string, Dossier>>({});

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hover, setHover] = useState<{ c: Candidate; x: number; y: number } | null>(null);
  const [showDocumented, setShowDocumented] = useState(true);
  const [region, setRegion] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("impact");
  const [intro, setIntro] = useState(true);
  const [swarmOpen, setSwarmOpen] = useState(false);
  const [focus, setFocus] = useState<FocusTarget | null>(null);
  const [fitNonce, setFitNonce] = useState(0);
  const nonce = useRef(0);

  useEffect(() => {
    loadDocumented().then(setDocumented).catch(console.error);
    loadCandidates().then(setCandidates).catch(console.error);
    loadHeroes().then(setHeroes).catch(() => {});
    loadMeta().then(setMeta).catch(console.error);
    loadDossiers().then(setDossiers).catch(() => {});
  }, []);

  const byId = useMemo(() => {
    const m = new Map<string, Candidate>();
    [...heroes, ...candidates].forEach((c) => m.set(c.well_id, c));
    return m;
  }, [heroes, candidates]);

  const regions = useMemo(
    () => (meta ? Object.keys(meta.candidate_by_region) : []),
    [meta]
  );

  const items = useMemo(() => {
    let list = candidates;
    if (region !== "all") list = list.filter((c) => c.county_group === region);
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(
        (c) =>
          c.quad_name?.toLowerCase().includes(q) ||
          c.state.toLowerCase().includes(q) ||
          c.enrichment?.nearest_school?.toLowerCase().includes(q) ||
          c.enrichment?.county?.toLowerCase().includes(q)
      );
    }
    const sorted = [...list];
    if (sortKey === "population")
      sorted.sort((a, b) => (b.enrichment?.population ?? 0) - (a.enrichment?.population ?? 0));
    else if (sortKey === "schools")
      sorted.sort(
        (a, b) => (b.enrichment?.schools_within_1mi ?? 0) - (a.enrichment?.schools_within_1mi ?? 0)
      );
    else sorted.sort((a, b) => a.rank - b.rank);
    const heroMatch =
      region === "all" && !query.trim() ? heroes : [];
    return [...heroMatch, ...sorted];
  }, [candidates, heroes, region, query, sortKey]);

  const selected = selectedId ? byId.get(selectedId) ?? null : null;

  function select(id: string) {
    const c = byId.get(id);
    if (!c) return;
    setSelectedId(id);
    nonce.current += 1;
    setFocus({ lon: c.lon, lat: c.lat, zoom: c.hero ? 15 : 13.5, nonce: nonce.current });
  }

  return (
    <main className="vignette relative h-screen w-screen overflow-hidden bg-ink-950">
      <MapView
        documented={documented}
        candidates={candidates}
        heroes={heroes}
        selectedId={selectedId}
        showDocumented={showDocumented}
        focus={focus}
        fitNonce={fitNonce}
        onSelect={select}
        onHover={(c, x, y) => setHover(c ? { c, x, y } : null)}
      />

      {/* brand + stat ribbon */}
      <div className="pointer-events-none absolute left-0 right-0 top-0 z-20 flex items-start justify-between p-5">
        <div className="pointer-events-auto">
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full rounded-full bg-ember opacity-60 animate-pulsering" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-ember" />
            </span>
            <h1 className="font-display text-lg tracking-tight text-paper">Lost Wells</h1>
          </div>
          <p className="mt-0.5 max-w-xs text-[11px] leading-snug text-ink-400">
            Finding America&apos;s undocumented orphaned oil &amp; gas wells — and ranking them by
            who&apos;s living on top of them.
          </p>
        </div>

        <div className="pointer-events-auto flex items-center gap-2">
          <button
            onClick={() => setSwarmOpen((v) => !v)}
            className={`rounded-lg border px-3 py-1.5 text-[11px] font-medium transition-colors ${
              swarmOpen
                ? "border-ember/50 bg-ember/15 text-ember-soft"
                : "border-white/10 bg-ink-900/70 text-ink-300 hover:text-ink-100"
            }`}
          >
            ◆ Agent swarm
          </button>
          <button
            onClick={() => setIntro(true)}
            className="rounded-lg border border-white/10 bg-ink-900/70 px-3 py-1.5 text-[11px] font-medium text-ink-300 hover:text-ink-100"
          >
            About
          </button>
        </div>
      </div>

      {/* left sidebar */}
      <div className="absolute bottom-0 left-0 top-0 z-20 flex w-[380px] flex-col border-r border-white/[0.06] bg-ink-900/80 backdrop-blur-md">
        <div className="px-4 pb-3 pt-20">
          <div className="flex items-baseline justify-between">
            <h2 className="font-display text-sm text-ink-200">Ranked candidates</h2>
            <span className="tnum text-[11px] text-ink-500">
              {fmtInt(items.length)} of {fmtInt(candidates.length)}
            </span>
          </div>
          <div className="mt-2.5 flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search quad, county, school…"
              className="min-w-0 flex-1 rounded-lg border border-white/10 bg-ink-850 px-2.5 py-1.5 text-[12px] text-ink-100 placeholder:text-ink-500 focus:border-ember/40 focus:outline-none"
            />
          </div>
          <div className="mt-2 flex gap-2">
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="flex-1 rounded-lg border border-white/10 bg-ink-850 px-2 py-1.5 text-[11px] text-ink-200 focus:outline-none"
            >
              <option value="all">All regions</option>
              {regions.map((r) => (
                <option key={r} value={r}>
                  {r.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="flex-1 rounded-lg border border-white/10 bg-ink-850 px-2 py-1.5 text-[11px] text-ink-200 focus:outline-none"
            >
              <option value="impact">Sort: Impact</option>
              <option value="population">Sort: Population</option>
              <option value="schools">Sort: Schools</option>
            </select>
          </div>
        </div>
        <div className="flex-1 overflow-hidden border-t border-white/[0.06]">
          <RankedList
            items={items}
            selectedId={selectedId}
            onSelect={select}
            onHover={(id) => {
              if (!id) setHover(null);
            }}
          />
        </div>
        <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-2.5 text-[10px] text-ink-500">
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={showDocumented}
              onChange={(e) => setShowDocumented(e.target.checked)}
              className="accent-teal"
            />
            Show {meta ? fmtInt(meta.documented_count) : "117,672"} documented
          </label>
          <button onClick={() => setFitNonce((n) => n + 1)} className="hover:text-ink-200">
            Reset view
          </button>
        </div>
      </div>

      {/* dossier panel */}
      <AnimatePresence>
        {selected && (
          <motion.div
            initial={{ x: 60, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 60, opacity: 0 }}
            transition={{ type: "spring", stiffness: 180, damping: 24 }}
            className="absolute bottom-0 right-0 top-0 z-30 w-[420px] border-l border-white/[0.06] bg-ink-900/90 shadow-panel backdrop-blur-md"
          >
            <DossierPanel
              candidate={selected}
              dossier={dossiers[selected.well_id]}
              onClose={() => setSelectedId(null)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* agent swarm panel */}
      <SwarmPanel open={swarmOpen} candidates={candidates} dossiers={dossiers} onClose={() => setSwarmOpen(false)} onSelect={select} />

      {/* hover tooltip */}
      {hover && (
        <div
          className="pointer-events-none absolute z-40 -translate-x-1/2 -translate-y-[calc(100%+14px)] rounded-lg border border-white/10 bg-ink-900/95 px-3 py-2 shadow-panel"
          style={{ left: hover.x + 380, top: hover.y }}
        >
          <div className="flex items-center gap-2">
            <span
              className="tnum flex h-6 w-6 items-center justify-center rounded text-[11px] font-bold text-ink-950"
              style={{ background: scoreCSS(hover.c.score.composite) }}
            >
              {Math.round(hover.c.score.composite)}
            </span>
            <span className="text-[12px] font-medium text-ink-100">
              {hover.c.hero?.title ?? hover.c.quad_name}
            </span>
          </div>
          <div className="tnum mt-1 text-[10px] text-ink-400">
            {fmtInt(hover.c.enrichment?.population)} nearby ·{" "}
            {hover.c.enrichment?.schools_within_1mi ?? 0} schools ≤1mi
          </div>
        </div>
      )}

      <Legend showDocumented={showDocumented} />

      <IntroOverlay
        open={intro}
        onClose={() => setIntro(false)}
        documentedCount={meta?.documented_count ?? 117672}
        candidateCount={meta?.candidate_count ?? 1303}
      />
    </main>
  );
}
