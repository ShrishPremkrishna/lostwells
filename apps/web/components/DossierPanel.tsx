"use client";

import { motion } from "framer-motion";
import type { Candidate, Dossier } from "@/lib/types";
import { METRIC_LABELS } from "@/lib/types";
import { scoreCSS } from "@/lib/colors";
import { ScoreBar } from "./ScoreBar";
import { fmtInt, fmtUSD, fmtPct, fmtMiles, fmtTonnes } from "@/lib/format";

function Card({ title, accent, children }: { title: string; accent?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-ink-850/60 p-3.5">
      <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
        {accent && <span className="h-2 w-2 rounded-full" style={{ background: accent }} />}
        {title}
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-ink-500">{label}</div>
      <div className="tnum text-lg font-semibold text-ink-100">{value}</div>
      {sub && <div className="text-[10px] text-ink-400">{sub}</div>}
    </div>
  );
}

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};
const item = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0 },
};

export function DossierPanel({
  candidate,
  dossier,
  onClose,
  onInvestigate,
  investigating,
}: {
  candidate: Candidate;
  dossier?: Dossier;
  onClose: () => void;
  onInvestigate?: (id: string) => void;
  investigating?: boolean;
}) {
  const c = candidate;
  const e = c.enrichment || {};
  const s = c.score;
  const m = c.methane;
  const p = c.plug_cost;
  const cb = c.carbon;

  return (
    <motion.div
      key={c.well_id}
      variants={stagger}
      initial="hidden"
      animate="show"
      className="flex h-full flex-col"
    >
      {/* header */}
      <motion.div variants={item} className="border-b border-white/[0.06] p-5 pb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              {c.hero ? (
                <span className="rounded bg-danger/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-danger">
                  Confirmed exposure
                </span>
              ) : (
                <span className="rounded bg-ember/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ember-soft">
                  Undocumented · U-Net
                </span>
              )}
              <span className="tnum text-[11px] text-ink-400">Rank #{c.rank}</span>
            </div>
            <h2 className="font-display mt-1.5 text-xl leading-tight text-paper">
              {c.hero?.title ?? `${c.quad_name ?? c.name}`}
            </h2>
            <p className="mt-0.5 text-xs text-ink-300">
              {c.hero?.place ?? `${e.county ?? c.county_group?.replace(/_/g, " ")}, ${c.state}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-white/10 px-2 py-1 text-ink-400 hover:bg-white/5 hover:text-ink-100"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {c.hero?.blurb && (
          <p className="mt-3 border-l-2 border-danger/50 pl-3 text-[13px] leading-relaxed text-ink-200">
            {c.hero.blurb}
          </p>
        )}

        <div className="mt-4 flex items-center gap-4">
          <div
            className="tnum flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-xl text-ink-950"
            style={{ background: scoreCSS(s.composite) }}
          >
            <span className="text-2xl font-bold leading-none">{Math.round(s.composite)}</span>
            <span className="text-[8px] font-semibold uppercase tracking-wide opacity-80">impact</span>
          </div>
          <div className="flex-1">
            <ScoreBar groups={s.group_breakdown} composite={s.composite} height={10} showLegend />
          </div>
        </div>
      </motion.div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {/* breakdown */}
        <motion.div variants={item}>
          <Card title="Why it ranks here">
            <div className="space-y-1.5">
              {Object.entries(s.breakdown)
                .sort((a, b) => b[1] - a[1])
                .map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2">
                    <span className="w-40 shrink-0 text-[11px] text-ink-300">
                      {METRIC_LABELS[k] ?? k}
                    </span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-800">
                      <div
                        className="h-full rounded-full bg-ember/70"
                        style={{ width: `${Math.min(100, (v / Math.max(...Object.values(s.breakdown))) * 100)}%` }}
                      />
                    </div>
                    <span className="tnum w-9 shrink-0 text-right text-[11px] text-ink-200">
                      {v.toFixed(1)}
                    </span>
                  </div>
                ))}
            </div>
            {s.missing_metrics.length > 0 && (
              <p className="mt-2 text-[10px] text-ink-500">
                Renormalized (no data): {s.missing_metrics.map((x) => METRIC_LABELS[x] ?? x).join(", ")}
              </p>
            )}
          </Card>
        </motion.div>

        {/* exposure */}
        <motion.div variants={item}>
          <Card title="Human exposure" accent="#ff7a18">
            <div className="grid grid-cols-3 gap-3">
              <Stat label="Pop. (tract)" value={fmtInt(e.population)} />
              <Stat label="Daytime pop." value={fmtInt(e.daytime_population)} />
              <Stat label="Schools ≤1mi" value={e.schools_within_1mi ?? "—"} />
            </div>
            {e.nearest_school && (
              <p className="mt-2 text-[11px] text-ink-300">
                Nearest school: <span className="text-ink-100">{e.nearest_school}</span>{" "}
                <span className="tnum text-ink-400">({fmtMiles(e.nearest_school_m)})</span>
              </p>
            )}
            {e.school_names && e.school_names.length > 1 && (
              <p className="mt-1 text-[10px] leading-relaxed text-ink-500">
                {e.school_names.slice(0, 6).join(" · ")}
              </p>
            )}
          </Card>
        </motion.div>

        {/* equity */}
        <motion.div variants={item}>
          <Card title="Equity & vulnerability" accent="#f5a623">
            <div className="grid grid-cols-3 gap-3">
              <Stat label="SVI pct" value={fmtPct(e.svi)} sub="CDC/ATSDR 2022" />
              <Stat label="Poverty" value={e.poverty_pct != null ? `${e.poverty_pct}%` : "—"} sub="≤150% FPL" />
              <Stat label="People of color" value={e.minority_pct != null ? `${e.minority_pct}%` : "—"} />
            </div>
            <p className="mt-2 text-[10px] text-ink-500">
              EJ demographic-index proxy {fmtPct(e.ej, 0)} — mean of low-income + people-of-color
              share (stands in for the federally-removed EJScreen).
            </p>
          </Card>
        </motion.div>

        {/* methane */}
        <motion.div variants={item}>
          <Card title="Methane proxy" accent="#9ca3af">
            <div className="grid grid-cols-2 gap-3">
              <Stat
                label="Emission rate"
                value={`${m.g_per_hr_point} g/hr`}
                sub={`range ${m.g_per_hr_low}–${m.g_per_hr_high}`}
              />
              <Stat
                label="CO₂e (GWP-100)"
                value={`${m.t_co2e_gwp100_point} t/yr`}
                sub={`${m.t_co2e_gwp20_point} t/yr at GWP-20`}
              />
            </div>
            <p className="mt-2 text-[10px] text-ink-500">{m.label}</p>
          </Card>
        </motion.div>

        {/* economics */}
        <motion.div variants={item}>
          <Card title="Plugging economics" accent="#2dd4bf">
            <div className="grid grid-cols-2 gap-3">
              <Stat
                label="Est. plug + reclaim"
                value={fmtUSD(p.point_usd)}
                sub={`${fmtUSD(p.low_usd)}–${fmtUSD(p.high_usd)}`}
              />
              <Stat label="Plug-only" value={fmtUSD(p.plug_only_usd)} sub={p.is_gas ? "gas +9%" : "oil basis"} />
            </div>
            {!p.depth_known && (
              <p className="mt-2 text-[10px] text-ink-500">
                Depth unknown in source → base estimate (Raimi et al. 2021), no depth premium applied.
              </p>
            )}
          </Card>
        </motion.div>

        {/* carbon kicker */}
        <motion.div variants={item}>
          <Card title="Carbon-credit kicker (honest)">
            <div className="grid grid-cols-2 gap-3">
              <Stat
                label="Lifetime credit value"
                value={fmtUSD(cb.value_point_usd)}
                sub={`${fmtUSD(cb.value_low_usd)}–${fmtUSD(cb.value_high_usd)} · ${fmtTonnes(cb.creditable_tonnes, 1)} CO₂e`}
              />
              <Stat
                label="Covers plug cost?"
                value={cb.pencils_out ? "Maybe" : "No"}
                sub={`${(cb.self_funding_ratio_point * 100).toFixed(1)}% of cost`}
              />
            </div>
            <p className="mt-2 text-[10px] text-ink-500">{cb.label}. Most wells need public funds.</p>
          </Card>
        </motion.div>

        {/* provenance */}
        <motion.div variants={item}>
          <Card title="Detection provenance">
            <p className="text-[11px] leading-relaxed text-ink-300">
              {c.hero ? (
                <>Documented well with confirmed exposure history.</>
              ) : (
                <>
                  Detected by the LBNL CATALOG U-Net on the{" "}
                  <span className="text-ink-100">
                    {c.quad_year} {c.quad_name} 1:{Number(c.quad_scale).toLocaleString()}
                  </span>{" "}
                  historical topographic quad. Nearest documented well:{" "}
                  <span className="tnum text-ink-100">{fmtMiles(c.nearest_doc_well_m)}</span> away
                  (&gt;100 m ⇒ candidate undocumented orphaned well).
                </>
              )}
            </p>
          </Card>
        </motion.div>

        {/* agent investigation */}
        <motion.div variants={item}>
          <InvestigationSection
            candidate={c}
            dossier={dossier}
            investigating={investigating}
            onInvestigate={onInvestigate}
          />
        </motion.div>
      </div>
    </motion.div>
  );
}

function InvestigationSection({
  candidate,
  dossier,
  investigating,
  onInvestigate,
}: {
  candidate: Candidate;
  dossier?: Dossier;
  investigating?: boolean;
  onInvestigate?: (id: string) => void;
}) {
  return (
    <div className="rounded-xl border border-ember/20 bg-gradient-to-b from-ember/[0.06] to-transparent p-3.5">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ember-soft">
          <span className="relative flex h-2 w-2">
            {investigating && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ember opacity-75" />
            )}
            <span className="relative inline-flex h-2 w-2 rounded-full bg-ember" />
          </span>
          Claude investigation
        </div>
        {dossier?.generated_by && (
          <span className="text-[9px] text-ink-500">{dossier.generated_by}</span>
        )}
      </div>

      {investigating ? (
        <div className="space-y-2">
          {["Searching operator history…", "Checking bankruptcy & shell transfers…", "Scanning local news…"].map(
            (t) => (
              <div key={t} className="flex items-center gap-2 text-[11px] text-ink-300">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ember" />
                {t}
              </div>
            )
          )}
        </div>
      ) : dossier && dossier.narrative ? (
        <div className="space-y-2.5 text-[12px] leading-relaxed text-ink-200">
          {dossier.narrative && <p>{dossier.narrative}</p>}
          {dossier.operator_history && (
            <Finding label="Operator" text={dossier.operator_history} />
          )}
          {dossier.bankruptcy_findings && (
            <Finding label="Liability" text={dossier.bankruptcy_findings} />
          )}
          {dossier.news_findings && <Finding label="In the news" text={dossier.news_findings} />}
          {dossier.sources && dossier.sources.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {dossier.sources.slice(0, 6).map((src, i) => (
                <a
                  key={i}
                  href={src.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-ink-300 hover:border-ember/40 hover:text-ember-soft"
                >
                  {src.title.slice(0, 28)}
                </a>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="text-[12px] text-ink-400">
          <p>
            No cached dossier for this well. An investigator agent searches operator history,
            bankruptcy filings, and local news via Claude + web search.
          </p>
          {onInvestigate && (
            <button
              onClick={() => onInvestigate(candidate.well_id)}
              className="mt-2.5 rounded-lg border border-ember/40 bg-ember/10 px-3 py-1.5 text-[11px] font-medium text-ember-soft hover:bg-ember/20"
            >
              ▶ Investigate live
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Finding({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <span className="mr-1.5 rounded bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-ink-400">
        {label}
      </span>
      <span>{text}</span>
    </div>
  );
}
