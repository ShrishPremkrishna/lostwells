"use client";

import { useEffect, useState } from "react";
import { loadKnowledge } from "@/lib/data";
import type { KnowledgeEntry } from "@/lib/types";

const TOPIC_LABEL: Record<string, string> = {
  state_program: "State plugging programs",
  funder: "Funders & charities",
  carbon_program: "Carbon programs",
  parcel_lookup: "Parcel / owner lookup",
  funding: "Federal funding",
  operator: "Operators found",
};

export function KnowledgeList() {
  const [items, setItems] = useState<KnowledgeEntry[]>([]);
  useEffect(() => {
    loadKnowledge().then(setItems).catch(() => {});
  }, []);
  if (!items.length) return null;

  const byTopic = new Map<string, KnowledgeEntry[]>();
  for (const e of items) {
    (byTopic.get(e.topic) ?? byTopic.set(e.topic, []).get(e.topic)!).push(e);
  }

  return (
    <div>
      <p className="text-[13px]" style={{ color: "var(--color-mid)" }}>
        {items.length} reusable findings the agent swarm has logged so far (state programs,
        funders, carbon routes, parcel lookups, operators) — so it never re-derives them.
      </p>
      <div className="mt-4 space-y-4">
        {[...byTopic.entries()].map(([topic, entries]) => (
          <div key={topic}>
            <div className="text-[11px] uppercase tracking-[0.08em]" style={{ color: "var(--color-mid)" }}>
              {TOPIC_LABEL[topic] ?? topic}
            </div>
            <ul className="mt-1 space-y-1">
              {entries.slice(0, 8).map((e) => (
                <li
                  key={e.key}
                  className="border-l-2 pl-3 text-[13px] leading-snug"
                  style={{ borderColor: "var(--color-accent)", color: "var(--color-text-body)" }}
                >
                  {e.value}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
