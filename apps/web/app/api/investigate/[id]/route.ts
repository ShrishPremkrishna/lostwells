import type { NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import fs from "node:fs";
import path from "node:path";
import { redisGet, redisSet } from "@/lib/redis-cache";

// Live, on-any-well investigation (§3.8). Ports services/swarm/investigator.py:
// official SDK + server-side web_search, streaming (keeps the connection alive
// during search), pause_turn continuation, source extraction, <dossier> parse.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const MODEL = process.env.SWARM_MODEL || "claude-sonnet-4-6";

// Single root .env serves both the Python pipeline and this route: fall back to
// reading ../../.env (repo root) when the var isn't already in the environment.
function apiKey(): string | undefined {
  if (process.env.ANTHROPIC_API_KEY) return process.env.ANTHROPIC_API_KEY;
  try {
    const txt = fs.readFileSync(path.join(process.cwd(), "..", "..", ".env"), "utf8");
    const m = txt.match(/^\s*(?:export\s+)?ANTHROPIC_API_KEY\s*=\s*(.+?)\s*$/m);
    if (m) return m[1].trim().replace(/^["']|["']$/g, "");
  } catch {
    /* ignore */
  }
  return undefined;
}

const SYSTEM =
  "You are an investigative analyst building a case file on a likely undocumented " +
  "orphaned oil or gas well. Doctrine: (1) GEOLOCATE FIRST — a raw lat/long is " +
  "invisible to search; resolve it to county + municipality (and an API well number " +
  "if findable) before searching those names. (2) Prefer authoritative databases " +
  "(state O&G regulator, SoS corporate registry, county records) over open web. " +
  "(3) Ladder each question 3–5 ways; rank sources by authority (gov/regulator > " +
  "court/SoS > news > aggregators). (4) Pivot on entities: operator → officers → " +
  "bankruptcy → successor → current responsible party. (5) Triangulate; never invent " +
  "an operator, date, or citation — say 'Not found on the record.' when unproven. " +
  "Undocumented wells usually have NO named operator; that itself is a finding.\n\n" +
  "OUTPUT FORMAT — STRICT: do at most 4 web searches, then reply with ONLY a JSON " +
  "object wrapped in <dossier> and </dossier>. No preamble, no markdown, no headers, " +
  "no emoji. Exactly these string keys: \"narrative\" (2–3 plain sentences for a " +
  "decision-maker), \"operator_history\", \"bankruptcy_findings\", \"news_findings\". " +
  "Each value is plain prose. Use \"Not found on the record.\" for anything unproven. " +
  "Example: <dossier>{\"narrative\":\"...\",\"operator_history\":\"...\"," +
  "\"bankruptcy_findings\":\"...\",\"news_findings\":\"...\"}</dossier>";

function brief(w: Record<string, unknown>): string {
  const e = (w.enrichment as Record<string, unknown>) || {};
  return [
    `Well id: ${w.well_id}`,
    `Location: ${w.lat}, ${w.lon} (${e.county ?? w.county_group ?? "?"}, ${w.state})`,
    `Detected on the ${w.quad_year ?? "?"} ${w.quad_name ?? "?"} USGS 1:24000 topographic quad.`,
    `Nearby: ~${e.population_1mi ?? e.population ?? "?"} people within 1 mile, ` +
      `${e.schools_within_1mi ?? 0} schools within 1 mile.`,
  ].join("\n");
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function extract(message: any): { text: string; sources: { title: string; url: string }[] } {
  const parts: string[] = [];
  const sources: { title: string; url: string }[] = [];
  const seen = new Set<string>();
  const add = (url?: string, title?: string) => {
    if (url && !seen.has(url)) {
      seen.add(url);
      sources.push({ title: (title || url).slice(0, 90), url });
    }
  };
  for (const block of message?.content ?? []) {
    if (block.type === "text") {
      parts.push(block.text || "");
      for (const c of block.citations || []) add(c.url, c.title);
    } else if (block.type === "web_search_tool_result") {
      for (const r of block.content || []) add(r.url, r.title);
    }
  }
  return { text: parts.join("\n"), sources };
}

function parseDossier(text: string): Record<string, string> {
  const m = text.match(/<dossier>([\s\S]*?)<\/dossier>/);
  if (m) {
    try {
      return JSON.parse(m[1].trim());
    } catch {
      try {
        const b = m[1];
        return JSON.parse(b.slice(b.indexOf("{"), b.lastIndexOf("}") + 1));
      } catch {
        /* fall through */
      }
    }
  }
  return { narrative: text.trim().slice(0, 600) };
}

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const key = apiKey();
  const well = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const enc = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (o: unknown) => controller.enqueue(enc.encode(`data: ${JSON.stringify(o)}\n\n`));
      const e = (well.enrichment as Record<string, unknown>) || {};
      if (!key) {
        send({ type: "error", text: "ANTHROPIC_API_KEY not configured." });
        controller.close();
        return;
      }
      send({ type: "status", text: `Geolocating ${well.quad_name ?? params.id} → ${e.county ?? well.state}…` });
      // Redis cache (sponsor): a prior investigation of this well returns instantly.
      const cached = (await redisGet(params.id)) as Record<string, unknown> | null;
      if (cached && cached.narrative) {
        send({ type: "status", text: "Cache hit — returning a prior investigation (Redis)." });
        send({ type: "dossier", dossier: cached });
        controller.close();
        return;
      }
      const client = new Anthropic({ apiKey: key });
      try {
        const messages: any[] = [{ role: "user", content: brief(well) }];
        let final: any = null;
        for (let i = 0; i < 4; i++) {
          send({ type: "status", text: "Searching public records, registries & local news…" });
          const s = client.messages.stream({
            model: MODEL,
            max_tokens: 3000,
            system: SYSTEM,
            messages,
            tools: [{ type: "web_search_20250305", name: "web_search", max_uses: 4 }] as any,
          });
          final = await s.finalMessage();
          if (final.stop_reason !== "pause_turn") break;
          messages.push({ role: "assistant", content: final.content });
        }
        const { text, sources } = extract(final);
        const dossier = parseDossier(text);
        const out = { ...dossier, well_id: params.id, sources: sources.slice(0, 8), generated_by: MODEL, status: "complete" };
        for (const src of sources.slice(0, 8)) send({ type: "source", ...src });
        send({ type: "dossier", dossier: out });
        await redisSet(params.id, out); // persist for instant repeats (sponsor cache)
      } catch (err: any) {
        send({ type: "error", text: String(err?.message || err).slice(0, 200) });
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
