import { TopBar } from "@/components/TopBar";
import { KnowledgeList } from "@/components/KnowledgeList";

export const metadata = { title: "About — Finding the Lost Wells of Appalachia" };

function Section({ label, title, children }: { label: string; title: string; children: React.ReactNode }) {
  return (
    <section className="border-t py-10" style={{ borderColor: "var(--color-base)" }}>
      <div className="mb-2 text-[11px] uppercase tracking-[0.08em]" style={{ color: "var(--color-mid)" }}>
        {label}
      </div>
      <h2 className="font-display text-2xl" style={{ color: "var(--color-text-head)" }}>
        {title}
      </h2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed" style={{ color: "var(--color-text-body)" }}>
        {children}
      </div>
    </section>
  );
}

export default function AboutPage() {
  return (
    <main className="flex h-screen flex-col" style={{ background: "var(--color-surface-1)" }}>
      <TopBar />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 pb-24 pt-12">
          <div className="text-[11px] uppercase tracking-[0.08em]" style={{ color: "var(--color-mid)" }}>
            Investigative geospatial tool
          </div>
          <h1 className="mt-2 font-display text-4xl leading-tight" style={{ color: "var(--color-text-head)" }}>
            We went looking for the wells nobody has on record.
          </h1>
          <p className="mt-5 text-[17px] leading-relaxed" style={{ color: "var(--color-text-body)" }}>
            There are an estimated 310,000–800,000 undocumented orphaned oil &amp; gas
            wells in the United States — versus only 117,672 documented ones. For the
            undocumented majority, human exposure is literally uncounted: a well can sit
            under a school gym or feet from a family&apos;s drinking water with no record
            at all. We set out to find them and rank them by who they hurt.
          </p>

          <Section label="The problem" title="The record is the gap">
            <p>
              The federal government has a finite <strong>$4.7B</strong> fund to plug
              orphaned wells. The catch: you can only plug a well you know exists. The
              documented inventory misses most of them, and roughly <strong>80%</strong>
              of the undocumented orphaned wells are concentrated in Appalachia — which is
              exactly where we focused.
            </p>
          </Section>

          <Section label="The discovery" title="36,919 wells, found overnight">
            <p>
              We ran a fine-tuned U-Net (after the LBNL CATALOG approach, Ciulla et al.
              2024) over digitized historical USGS topographic maps — the 1940s–1980s
              7.5-minute quads where old wells were drawn as symbols but never entered a
              modern database. In a single overnight run across four states (PA, WV, OH,
              KY) it surfaced <strong>36,919</strong> candidate undocumented wells.
              <strong> 38,095 of our candidates sit more than 100 m from any documented
              well</strong> (median ~1 km away) — genuinely off the record.
            </p>
            <p>
              We also include LBNL&apos;s published CA/OK detections (1,301) as a
              validation baseline — proof the method reproduces published work — but the
              headline, and the dashboard, is the Appalachia discovery.
            </p>
          </Section>

          <Section label="The pipeline" title="Discover → Diagnose → Act">
            <p>
              <strong>Discover</strong> consolidates the detections atop the 117,672-well
              documented backbone. <strong>Diagnose</strong> enriches every well with who
              lives on top of it — population within a mile, schools, drinking-water
              service areas, hospitals, social vulnerability, and environmental-justice
              burden — and ranks them on a transparent percentile composite.
              <strong> Act</strong> builds the case file: who is liable, who can fund the
              plug (federal program, state program, or carbon credits), and who can apply
              pressure, with a Claude agent swarm investigating the highest-impact wells.
            </p>
          </Section>

          <Section label="Methodology &amp; honesty" title="What is measured vs. modeled">
            <p>
              Ranking is driven by the six signals that actually differ between wells:
              population, schools, drinking water, hospitals, social vulnerability, and
              EJ burden. Methane and plug-cost are <em>modeled estimates</em> shown as
              context, not ranking signal — for undocumented detections they are
              class-level figures, and we label them as such.
            </p>
            <p>
              Detections are <em>high-confidence candidates</em>, never &quot;confirmed
              wells.&quot; The headline climate framing we trust is the cost one: at a
              modeled ~$76k per well it would cost about <strong>$2.9B</strong> to plug
              every well we found — inside the existing $4.7B fund. The problem was never
              the money. It was that nobody knew where the wells are.
            </p>
          </Section>

          <Section label="Living knowledge" title="What the agents have learned">
            <KnowledgeList />
          </Section>
        </div>
      </div>
    </main>
  );
}
