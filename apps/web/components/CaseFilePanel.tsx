"use client";

import type { Actor, CaseFile, Pathway, Regulator } from "@/lib/types";

const CONF: Record<string, string> = {
  high: "var(--color-accent)",
  medium: "var(--color-accent-soft)",
  low: "var(--color-mid)",
};

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-base bg-surface-2 p-3.5">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-mid">{title}</div>
      {children}
    </div>
  );
}

function PathwayRow({ p }: { p: Pathway }) {
  return (
    <div className="border-l-2 pl-3" style={{ borderColor: CONF[p.confidence] ?? "var(--color-base)" }}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-head">{p.label}</span>
        <span
          className="shrink-0 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-white"
          style={{ background: CONF[p.confidence] ?? "var(--color-mid)", borderRadius: 4 }}
        >
          {p.confidence}
        </span>
      </div>
      <p className="mt-0.5 text-[11px] leading-relaxed text-body">{p.rationale}</p>
      <p className="mt-0.5 text-[10px] text-mid">⏱ {p.timeline}</p>
    </div>
  );
}

function ActorRow({ role, name, sub, link, phone, email }: {
  role: string; name?: string | null; sub?: string | null;
  link?: string | null; phone?: string | null; email?: string | null;
}) {
  if (!name) return null;
  const href = email ? `mailto:${email}` : link || undefined;
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-base py-1.5 last:border-b-0">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.08em] text-mid">{role}</div>
        <div className="truncate text-[13px] text-head">{name}</div>
        {sub && <div className="truncate text-[10px] text-mid">{sub}</div>}
      </div>
      <div className="shrink-0 text-right text-[10px]">
        {phone && <div className="tnum text-body">{phone}</div>}
        {href && (
          <a href={href} target="_blank" rel="noreferrer" className="text-accent-deep hover:underline">
            {email ? "email" : "contact ↗"}
          </a>
        )}
      </div>
    </div>
  );
}

function leg(a: Actor) {
  return [a.party?.[0], a.district ? `Dist. ${a.district}` : null].filter(Boolean).join(" · ");
}

export function CaseFilePanel({ caseFile }: { caseFile?: CaseFile }) {
  if (!caseFile) return null;
  const { pathways, actors } = caseFile;
  const reg = actors.responsible_regulator as Regulator | null | undefined;
  const press = actors.can_pressure;
  const routeHref = reg?.email ? `mailto:${reg.email}` : reg?.url || undefined;

  return (
    <div className="space-y-3">
      <div className="border border-accent bg-accent-light p-3.5" style={{ borderColor: "var(--color-accent)" }}>
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--color-accent-ink)" }}>
          The case — who can plug it
        </div>
        <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "var(--color-accent-ink)" }}>
          We mobilize, we don&apos;t plug. Below is the funded path and the named people who can act.
        </p>
      </div>

      {pathways?.length > 0 && (
        <SectionCard title="How it gets plugged">
          <div className="space-y-2.5">
            {pathways.map((p) => <PathwayRow key={p.key} p={p} />)}
          </div>
        </SectionCard>
      )}

      <SectionCard title="Who can act">
        {actors.surface_owner?.owner && (
          <ActorRow
            role="Surface owner (parcel)"
            name={actors.surface_owner.owner}
            sub={[actors.surface_owner.owner_address,
                  actors.surface_owner.acres ? `${Math.round(actors.surface_owner.acres)} ac` : null]
                  .filter(Boolean).join(" · ")}
            link={actors.surface_owner.source_url}
          />
        )}
        <ActorRow
          role="Responsible · funder"
          name={reg?.agency}
          sub={[reg?.division, reg?.program].filter(Boolean).join(" — ")}
          link={reg?.url}
          phone={reg?.phone}
          email={reg?.email}
        />
        {press.us_representative && (
          <ActorRow
            role="U.S. Representative"
            name={press.us_representative.name}
            sub={press.us_representative.party}
            link={press.us_representative.url}
            phone={press.us_representative.phone}
          />
        )}
        {press.us_senators.map((s, i) => (
          <ActorRow key={i} role="U.S. Senator" name={s.name} sub={s.party} link={s.url} phone={s.phone} />
        ))}
        {press.state_legislators.map((s, i) => (
          <ActorRow key={i} role={`State ${s.chamber === "upper" ? "Senate" : "House"}`} name={s.name} sub={leg(s)} email={s.email} />
        ))}
        {press.ej_orgs.length > 0 && (
          <div className="pt-1.5">
            <div className="text-[10px] uppercase tracking-[0.08em] text-mid">Community / EJ allies</div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {press.ej_orgs.slice(0, 6).map((o, i) => (
                <a key={i} href={o.url} target="_blank" rel="noreferrer"
                   className="border border-base px-1.5 py-0.5 text-[10px] text-body hover:text-accent-deep">
                  {o.org}
                </a>
              ))}
            </div>
          </div>
        )}
      </SectionCard>

      {routeHref && reg?.agency && (
        <a
          href={routeHref}
          target="_blank"
          rel="noreferrer"
          className="block w-full px-3 py-2.5 text-center text-[12px] font-semibold uppercase tracking-[0.06em] text-white"
          style={{ background: "var(--color-accent)" }}
        >
          Route this well to {reg.agency.split("(")[0].trim()} →
        </a>
      )}
    </div>
  );
}
