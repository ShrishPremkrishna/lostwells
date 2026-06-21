import { TopBar } from "@/components/TopBar";

export const metadata = { title: "Contact — Finding the Lost Wells of Appalachia" };

export default function ContactPage() {
  return (
    <main className="flex h-screen flex-col" style={{ background: "var(--color-surface-1)" }}>
      <TopBar />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 pb-24 pt-12">
          <div className="text-[11px] uppercase tracking-[0.08em]" style={{ color: "var(--color-mid)" }}>
            Get in touch
          </div>
          <h1 className="mt-2 font-display text-4xl" style={{ color: "var(--color-text-head)" }}>
            Contact
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed" style={{ color: "var(--color-text-body)" }}>
            We are a routing / intelligence / advocacy layer — we mobilize, we do not
            plug wells or hold liability. If you are a regulator, a funder, a landowner,
            or a journalist working on orphaned wells, we&apos;d like to hear from you.
          </p>
          <div className="mt-8 space-y-px" style={{ background: "var(--color-base)" }}>
            {[
              ["Email", "hello@lostwells.example"],
              ["Project", "Finding the Lost Wells of Appalachia"],
              ["Devpost", "devpost.com"],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between p-4" style={{ background: "var(--color-surface-2)" }}>
                <span className="text-[11px] uppercase tracking-[0.08em]" style={{ color: "var(--color-mid)" }}>
                  {k}
                </span>
                <span className="font-mono text-[13px]" style={{ color: "var(--color-text-head)" }}>
                  {v}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
