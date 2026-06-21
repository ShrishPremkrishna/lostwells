"use client";

import { motion } from "framer-motion";
import type { Candidate, CaseFile, Dossier } from "@/lib/types";
import { METRIC_LABELS } from "@/lib/types";
import { scoreCSS } from "@/lib/colors";
import { CaseFilePanel } from "./CaseFilePanel";
import { fmtInt, fmtPct, fmtMiles } from "@/lib/format";

// First clean sentence of an LLM field (strip markdown, cap length).
function firstSentence(t?: string | null): string | null {
  if (!t) return null;
  const s = t.replace(/[#*`]/g, "").replace(/\s+/g, " ").trim();
  const m = s.match(/^.*?[.!?](\s|$)/);
  return (m ? m[0] : s).trim().slice(0, 180);
}

// Short, scannable, direct fact rows — the well at a glance. Deterministic facts +
// the agent's concise findings (operator / liability / news) when investigated.
function summaryRows(c: Candidate, dossier?: Dossier): [string, string][] {
  const e = c.enrichment || {};
  const pop = e.population_1mi ?? e.population;
  const rows: [string, string][] = [];
  rows.push(["Where", `${e.county ?? c.county_group?.replace(/_/g, " ") ?? "—"}, ${c.state}`]);
  rows.push([
    "Found",
    `${c.quad_year ?? ""} ${c.quad_name ?? ""} quad` +
      (c.nearest_doc_well_m != null ? ` · ${fmtMiles(c.nearest_doc_well_m)} from any documented well` : ""),
  ]);
  if (pop != null)
    rows.push([
      "Exposed",
      `~${fmtInt(pop)} within 1 mi` +
        ((e.schools_within_1mi ?? 0) > 0 ? ` · ${e.schools_within_1mi} school${e.schools_within_1mi === 1 ? "" : "s"}` : "") +
        (e.nearest_school ? ` · nearest school ${e.nearest_school}` : ""),
    ]);
  const op = firstSentence(dossier?.operator_history);
  rows.push(["Operator", op && !op.toLowerCase().startsWith("not found") ? op : "Undocumented — none on record"]);
  const bk = firstSentence(dossier?.bankruptcy_findings);
  if (bk && !bk.toLowerCase().startsWith("not found")) rows.push(["Liability", bk]);
  const nw = firstSentence(dossier?.news_findings);
  if (nw && !nw.toLowerCase().startsWith("not found")) rows.push(["In the news", nw]);
  return rows;
}

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.04 } } };
const item = { hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } };

function KeyStat({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div className="border border-base bg-surface-2 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-[0.06em] text-mid">{label}</div>
      <div className="tnum font-display text-base" style={{ color: color ?? "var(--color-text-head)" }}>
        {value}
      </div>
    </div>
  );
}

export function DossierPanel({
  candidate,
  dossier,
  caseFile,
  onClose,
  onInvestigate,
  investigating,
  liveLog,
  onTopoDissolve,
}: {
  candidate: Candidate;
  dossier?: Dossier;
  caseFile?: CaseFile;
  onClose: () => void;
  onInvestigate?: (id: string) => void;
  investigating?: boolean;
  liveLog?: string[];
  onTopoDissolve?: () => void;
}) {
  const c = candidate;
  const e = c.enrichment || {};
  const s = c.score;
  const pop = e.population_1mi ?? e.population;
  const rows = summaryRows(c, dossier);
  const sources = dossier?.sources || [];
  const maxBd = Math.max(...Object.values(s.breakdown), 0.0001);

  return (
    <motion.div key={c.well_id} variants={stagger} initial="hidden" animate="show" className="flex h-full flex-col">
      {/* minimal header — ID + rank only */}
      <motion.div variants={item} className="flex items-start justify-between gap-2 border-b border-base p-4">
        <div className="min-w-0">
          <div className="truncate font-mono text-[11px] text-head">{c.well_id}</div>
          <div className="text-[11px] text-mid">
            Rank #{c.rank}
            {c.hero ? " · featured discovery" : ""}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {onTopoDissolve && (
            <button
              onClick={onTopoDissolve}
              className="border border-base px-2 py-1 text-[10px] uppercase tracking-wide text-accent-deep hover:bg-accent-light"
            >
              Topo →
            </button>
          )}
          <button onClick={onClose} className="border border-base px-2 py-1 text-[11px] text-mid hover:text-head" aria-label="Close">
            ✕
          </button>
        </div>
      </motion.div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {/* 1. Summary + investigate (top) */}
        <motion.div variants={item}>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-mid">Summary</div>
          {investigating ? (
            <div className="space-y-1">
              {(liveLog && liveLog.length ? liveLog : ["Connecting to the agent…"]).map((t, i) => (
                <div key={i} className="flex items-start gap-2 font-mono text-[11px] text-body">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 animate-pulse" style={{ background: "var(--color-accent)" }} />
                  <span>{t}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1.5">
              {rows.map(([label, value]) => (
                <div key={label} className="flex gap-2 text-[12px] leading-snug">
                  <span className="w-[62px] shrink-0 pt-px text-[10px] uppercase tracking-[0.06em] text-mid">
                    {label}
                  </span>
                  <span className="text-body">{value}</span>
                </div>
              ))}
            </div>
          )}
          <button
            onClick={() => onInvestigate?.(c.well_id)}
            disabled={!onInvestigate || investigating}
            className="mt-2.5 w-full px-3 py-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-white disabled:opacity-50"
            style={{ background: "var(--color-accent)" }}
            title={onInvestigate ? "" : "Live route unavailable"}
          >
            {investigating ? "Investigating…" : dossier?.narrative ? "Re-investigate live" : "Run investigation"}
          </button>
          {sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {sources.slice(0, 6).map((src, i) => (
                <a
                  key={i}
                  href={src.url}
                  target="_blank"
                  rel="noreferrer"
                  className="border border-base px-1.5 py-0.5 text-[10px] text-body hover:text-accent-deep"
                >
                  {(src.url || "").includes("browserbase") ? "▶ session" : src.title.slice(0, 24)}
                </a>
              ))}
            </div>
          )}
        </motion.div>

        {/* 2. Key statistics (compact) */}
        <motion.div variants={item}>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-mid">Key stats</div>
          <div className="grid grid-cols-3 gap-1.5">
            <KeyStat label="Impact" value={Math.round(s.composite)} color={scoreCSS(s.composite)} />
            <KeyStat label="Pop · 1mi" value={fmtInt(pop)} />
            <KeyStat label="Schools ≤1mi" value={e.schools_within_1mi ?? "—"} />
            <KeyStat label="Social vuln." value={fmtPct(e.svi)} />
            <KeyStat label="EJ burden" value={fmtPct(e.eji_rank ?? e.ej)} />
            <KeyStat label="Poverty" value={e.poverty_pct != null ? `${e.poverty_pct}%` : "—"} />
          </div>
        </motion.div>

        {/* 3. Why it ranks here */}
        <motion.div variants={item}>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-mid">Why it ranks here</div>
          <div className="space-y-1.5">
            {Object.entries(s.breakdown)
              .sort((a, b) => b[1] - a[1])
              .map(([k, v]) => (
                <div key={k} className="flex items-center gap-2">
                  <span className="w-36 shrink-0 text-[11px] text-body">{METRIC_LABELS[k] ?? k}</span>
                  <div className="h-1.5 flex-1 overflow-hidden" style={{ background: "var(--color-base)" }}>
                    <div className="h-full" style={{ width: `${Math.min(100, (v / maxBd) * 100)}%`, background: "var(--color-accent)" }} />
                  </div>
                  <span className="tnum w-9 shrink-0 text-right text-[11px] text-head">{v.toFixed(1)}</span>
                </div>
              ))}
          </div>
        </motion.div>

        {/* 4 + 5. How it gets plugged + who can act */}
        {caseFile && (
          <motion.div variants={item}>
            <CaseFilePanel caseFile={caseFile} />
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
