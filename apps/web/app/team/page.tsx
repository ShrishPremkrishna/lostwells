import { TopBar } from "@/components/TopBar";

export const metadata = { title: "Team — Finding the Lost Wells of Appalachia" };

// Placeholder roster — fill with real names/roles before the demo.
const TEAM = [
  { name: "Team member", role: "ML / U-Net detection" },
  { name: "Team member", role: "Data pipeline / scoring engine" },
  { name: "Team member", role: "Agent swarm / Act layer" },
  { name: "Team member", role: "Design / front-end" },
];

export default function TeamPage() {
  return (
    <main className="flex h-screen flex-col" style={{ background: "var(--color-surface-1)" }}>
      <TopBar />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 pb-24 pt-12">
          <div className="text-[11px] uppercase tracking-[0.08em]" style={{ color: "var(--color-mid)" }}>
            Who built this
          </div>
          <h1 className="mt-2 font-display text-4xl" style={{ color: "var(--color-text-head)" }}>
            Team
          </h1>
          <div className="mt-8 grid grid-cols-1 gap-px sm:grid-cols-2" style={{ background: "var(--color-base)" }}>
            {TEAM.map((m, i) => (
              <div key={i} className="p-5" style={{ background: "var(--color-surface-2)" }}>
                <div className="font-display text-lg" style={{ color: "var(--color-text-head)" }}>
                  {m.name}
                </div>
                <div className="mt-1 text-[13px]" style={{ color: "var(--color-text-body)" }}>
                  {m.role}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-6 text-[13px]" style={{ color: "var(--color-mid)" }}>
            Built for the hackathon with Anthropic Claude, Redis, and Browserbase.
          </p>
        </div>
      </div>
    </main>
  );
}
