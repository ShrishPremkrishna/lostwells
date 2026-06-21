"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence, motion } from "framer-motion";
import type { FocusTarget } from "@/components/MapView";
import { TopBar } from "@/components/TopBar";
import { RankedList } from "@/components/RankedList";
import { DossierPanel } from "@/components/DossierPanel";
import { Legend } from "@/components/Legend";
import { IntroOverlay } from "@/components/IntroOverlay";
import { TopoDissolve } from "@/components/TopoDissolve";
import type { Candidate, CandidateLite, CaseFile, DocumentedWells, Dossier, Meta } from "@/lib/types";
import {
  loadCandidates,
  loadCaseFiles,
  loadDetailShard,
  loadDocumented,
  loadDossiers,
  loadHeroes,
  loadMeta,
  shardOf,
} from "@/lib/data";
import { fmtInt } from "@/lib/format";
import { scoreCSS } from "@/lib/colors";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

type SortKey = "impact" | "population" | "schools";

// The main view is the U-Net Appalachia discovery (the project's headline). CA/OK
// (LBNL's published baseline) is held out as a separate validation layer.
const APPALACHIA_STATES = new Set([
  "Ohio",
  "Pennsylvania",
  "West Virginia",
  "Kentucky",
]);

export default function Page() {
  const [documented, setDocumented] = useState<DocumentedWells | null>(null);
  const [candidates, setCandidates] = useState<CandidateLite[]>([]);
  const [heroes, setHeroes] = useState<Candidate[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [dossiers, setDossiers] = useState<Record<string, Dossier>>({});
  const [cases, setCases] = useState<Record<string, CaseFile>>({});

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailCache, setDetailCache] = useState<Record<string, Candidate>>({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [hover, setHover] = useState<{ c: CandidateLite; x: number; y: number } | null>(null);
  const [showDocumented, setShowDocumented] = useState(true);
  const [region, setRegion] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("impact");
  const [intro, setIntro] = useState(true);
  const [focus, setFocus] = useState<FocusTarget | null>(null);
  const [fitNonce, setFitNonce] = useState(0);
  const [topoHero, setTopoHero] = useState<Candidate | null>(null);
  const [investigatingId, setInvestigatingId] = useState<string | null>(null);
  const [liveLog, setLiveLog] = useState<string[]>([]);
  const nonce = useRef(0);

  useEffect(() => {
    loadDocumented().then(setDocumented).catch(console.error);
    loadCandidates().then(setCandidates).catch(console.error);
    loadHeroes().then(setHeroes).catch(() => {});
    loadMeta().then(setMeta).catch(console.error);
    loadDossiers().then(setDossiers).catch(() => {});
    loadCaseFiles().then(setCases).catch(() => {});
  }, []);

  // Default main view = Appalachia discovery only; CA/OK is the validation layer.
  // Heroes are featured separately (prepended + red markers), so drop them here to
  // avoid showing each twice.
  const heroIds = useMemo(() => new Set(heroes.map((h) => h.well_id)), [heroes]);
  const mainCandidates = useMemo(
    () => candidates.filter((c) => APPALACHIA_STATES.has(c.state) && !heroIds.has(c.well_id)),
    [candidates, heroIds]
  );

  const byId = useMemo(() => {
    const m = new Map<string, CandidateLite>();
    [...heroes, ...candidates].forEach((c) => m.set(c.well_id, c));
    return m;
  }, [heroes, candidates]);

  const heroById = useMemo(() => {
    const m = new Map<string, Candidate>();
    heroes.forEach((h) => m.set(h.well_id, h));
    return m;
  }, [heroes]);

  const regions = useMemo(
    () =>
      meta
        ? Object.keys(meta.candidate_by_region).filter((r) => /_(PA|OH|WV|KY)$/.test(r))
        : [],
    [meta]
  );

  const items = useMemo(() => {
    let list = mainCandidates;
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
      sorted.sort(
        (a, b) =>
          (b.enrichment?.population_1mi ?? b.enrichment?.population ?? 0) -
          (a.enrichment?.population_1mi ?? a.enrichment?.population ?? 0)
      );
    else if (sortKey === "schools")
      sorted.sort(
        (a, b) => (b.enrichment?.schools_within_1mi ?? 0) - (a.enrichment?.schools_within_1mi ?? 0)
      );
    else sorted.sort((a, b) => a.rank - b.rank);
    const heroMatch = region === "all" && !query.trim() ? heroes : [];
    return [...heroMatch, ...sorted];
  }, [mainCandidates, heroes, region, query, sortKey]);

  const selected = selectedId ? byId.get(selectedId) ?? null : null;
  const selectedDetail: Candidate | null = selectedId
    ? heroById.get(selectedId) ?? detailCache[selectedId] ?? null
    : null;

  function select(id: string) {
    const c = byId.get(id);
    if (!c) return;
    setSelectedId(id);
    nonce.current += 1;
    setFocus({ lon: c.lon, lat: c.lat, zoom: c.hero ? 15 : 13.5, nonce: nonce.current });
    if (heroById.has(id) || detailCache[id]) return;
    const shard = shardOf(c.rank);
    setDetailLoading(true);
    loadDetailShard(shard)
      .then((recs) => setDetailCache((prev) => ({ ...prev, ...recs })))
      .catch(console.error)
      .finally(() => setDetailLoading(false));
  }

  // Live, on-any-well investigation: stream the SSE route into the panel.
  async function investigateLive(well: Candidate) {
    setInvestigatingId(well.well_id);
    setLiveLog([]);
    try {
      const res = await fetch(`/api/investigate/${encodeURIComponent(well.well_id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(well),
      });
      const reader = res.body?.getReader();
      if (!reader) throw new Error("no stream");
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const f of frames) {
          const line = f.trim();
          if (!line.startsWith("data:")) continue;
          const evt = JSON.parse(line.slice(5).trim());
          if (evt.type === "status") setLiveLog((l) => [...l, evt.text]);
          else if (evt.type === "error") setLiveLog((l) => [...l, "⚠ " + evt.text]);
          else if (evt.type === "dossier")
            setDossiers((d) => ({ ...d, [well.well_id]: evt.dossier }));
        }
      }
    } catch {
      setLiveLog((l) => [...l, "⚠ investigation failed"]);
    } finally {
      setInvestigatingId(null);
    }
  }

  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden" style={{ background: "var(--color-surface-1)" }}>
      <TopBar />

      <div className="relative flex-1 overflow-hidden">
        <MapView
          documented={documented}
          candidates={mainCandidates}
          heroes={heroes}
          selectedId={selectedId}
          showDocumented={showDocumented}
          focus={focus}
          fitNonce={fitNonce}
          onSelect={select}
          onHover={(c, x, y) => setHover(c ? { c, x, y } : null)}
        />

        {/* left sidebar — the ranked candidate list */}
        <div
          className="absolute bottom-0 left-0 top-0 z-20 flex w-[360px] flex-col border-r"
          style={{ background: "var(--color-surface-2)", borderColor: "var(--color-base)" }}
        >
          <div className="px-4 pb-3 pt-4">
            <div className="flex items-baseline justify-between">
              <h2 className="font-display text-lg" style={{ color: "var(--color-text-head)" }}>
                Ranked candidates
              </h2>
              <span className="tnum text-[11px]" style={{ color: "var(--color-mid)" }}>
                {fmtInt(items.length)} of {fmtInt(mainCandidates.length)}
              </span>
            </div>
            <p className="mt-0.5 text-[11px]" style={{ color: "var(--color-mid)" }}>
              Wells we discovered in Appalachia, ranked by who lives on top of them.
            </p>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search quad, county, school…"
              className="mt-2.5 w-full border px-2.5 py-1.5 text-[12px] focus:outline-none"
              style={{ background: "#fff", borderColor: "var(--color-base)", color: "var(--color-text-body)" }}
            />
            <div className="mt-2 flex gap-2">
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="flex-1 border px-2 py-1.5 text-[11px] focus:outline-none"
                style={{ background: "#fff", borderColor: "var(--color-base)", color: "var(--color-text-body)" }}
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
                className="flex-1 border px-2 py-1.5 text-[11px] focus:outline-none"
                style={{ background: "#fff", borderColor: "var(--color-base)", color: "var(--color-text-body)" }}
              >
                <option value="impact">Sort: Impact</option>
                <option value="population">Sort: Population</option>
                <option value="schools">Sort: Schools</option>
              </select>
            </div>
          </div>
          <div className="flex-1 overflow-hidden border-t" style={{ borderColor: "var(--color-base)" }}>
            <RankedList
              items={items}
              selectedId={selectedId}
              onSelect={select}
              onHover={(id) => {
                if (!id) setHover(null);
              }}
            />
          </div>
          <div
            className="flex items-center justify-between border-t px-4 py-2.5 text-[10px]"
            style={{ borderColor: "var(--color-base)", color: "var(--color-mid)" }}
          >
            <label className="flex cursor-pointer items-center gap-1.5">
              <input
                type="checkbox"
                checked={showDocumented}
                onChange={(e) => setShowDocumented(e.target.checked)}
                style={{ accentColor: "var(--color-accent)" }}
              />
              Show {meta ? fmtInt(meta.documented_count) : "117,672"} documented
            </label>
            <button onClick={() => setFitNonce((n) => n + 1)} className="hover:underline">
              Reset view
            </button>
          </div>
        </div>

        {/* dossier panel — slides in over the map from the right */}
        <AnimatePresence>
          {selected && (
            <motion.div
              initial={{ x: 60, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 60, opacity: 0 }}
              transition={{ type: "spring", stiffness: 180, damping: 24 }}
              className="absolute bottom-0 right-0 top-0 z-30 w-[420px] border-l shadow-panel"
              style={{ background: "var(--color-surface-1)", borderColor: "var(--color-base)" }}
            >
              {selectedDetail ? (
                <DossierPanel
                  candidate={selectedDetail}
                  dossier={dossiers[selectedDetail.well_id]}
                  caseFile={cases[selectedDetail.well_id]}
                  onInvestigate={() => investigateLive(selectedDetail)}
                  investigating={investigatingId === selectedDetail.well_id}
                  liveLog={investigatingId === selectedDetail.well_id ? liveLog : undefined}
                  onClose={() => setSelectedId(null)}
                  onTopoDissolve={
                    selectedDetail.hero ? () => setTopoHero(selectedDetail) : undefined
                  }
                />
              ) : (
                <DossierSkeleton
                  lite={selected}
                  loading={detailLoading}
                  onClose={() => setSelectedId(null)}
                />
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* hover tooltip — dark "field notes on glass" over the map */}
        {hover && (
          <div
            className="pointer-events-none absolute z-40 -translate-x-1/2 -translate-y-[calc(100%+14px)] border px-3 py-2"
            style={{
              left: hover.x,
              top: hover.y,
              background: "rgba(13,13,13,0.88)",
              borderColor: "rgba(255,255,255,0.12)",
            }}
          >
            <div className="flex items-center gap-2">
              <span
                className="tnum flex h-6 w-6 items-center justify-center text-[11px] font-bold text-white"
                style={{ background: scoreCSS(hover.c.score.composite) }}
              >
                {Math.round(hover.c.score.composite)}
              </span>
              <span className="text-[12px] font-medium text-white">
                {hover.c.hero?.title ?? hover.c.quad_name}
              </span>
            </div>
            <div className="tnum mt-1 text-[10px]" style={{ color: "rgba(255,255,255,0.7)" }}>
              {fmtInt(hover.c.enrichment?.population_1mi ?? hover.c.enrichment?.population)} within 1 mi ·{" "}
              {hover.c.enrichment?.schools_within_1mi ?? 0} schools ≤1mi
            </div>
          </div>
        )}

        <Legend showDocumented={showDocumented} />
      </div>

      <IntroOverlay
        open={intro}
        onClose={() => setIntro(false)}
        meta={meta}
      />

      {topoHero && <TopoDissolve hero={topoHero} onClose={() => setTopoHero(null)} />}
    </main>
  );
}

// Lightweight placeholder shown while the heavy detail shard loads.
function DossierSkeleton({
  lite,
  loading,
  onClose,
}: {
  lite: CandidateLite;
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between border-b p-4" style={{ borderColor: "var(--color-base)" }}>
        <div className="flex items-center gap-3">
          <span
            className="tnum flex h-10 w-10 items-center justify-center text-base font-semibold text-white"
            style={{ background: scoreCSS(lite.score.composite) }}
          >
            {Math.round(lite.score.composite)}
          </span>
          <div>
            <div className="text-sm font-medium" style={{ color: "var(--color-text-head)" }}>
              {lite.hero?.title ?? lite.quad_name ?? lite.name}
            </div>
            <div className="text-[11px]" style={{ color: "var(--color-mid)" }}>
              {lite.hero?.place ?? lite.county_group?.replace(/_/g, " ") ?? lite.state}
              {loading && <span className="ml-1">· loading detail…</span>}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="border px-2 py-1 text-[11px]"
          style={{ borderColor: "var(--color-base)", color: "var(--color-mid)" }}
        >
          ✕
        </button>
      </div>
      <div className="flex-1 space-y-3 p-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-20 border" style={{ borderColor: "var(--color-base)", background: "var(--color-surface-2)" }} />
        ))}
      </div>
    </div>
  );
}
