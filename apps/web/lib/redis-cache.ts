// Redis dossier cache for the live route — twin of services/swarm/web/cache.py,
// same key scheme so the batch swarm and the live route share one cache.
// Graceful: tight timeouts + one-shot disable so an unreachable Redis never hangs
// the SSE route (it just falls through to a live investigation).
import { createClient } from "redis";
import fs from "node:fs";
import path from "node:path";

// Minimal surface — avoids node-redis's heavy generic types (this is a best-effort cache).
interface MiniRedis {
  connect(): Promise<unknown>;
  on(event: string, cb: (e?: unknown) => void): unknown;
  get(key: string): Promise<string | null>;
  set(key: string, value: string, opts?: { EX: number }): Promise<unknown>;
}

const TTL = 60 * 60 * 24 * 30; // 30 days
const KEY = (id: string) => `dossier:${id}`;

let client: MiniRedis | null = null;
let connecting: Promise<MiniRedis | null> | null = null;
let disabled = false;

function redisUrl(): string | undefined {
  if (process.env.REDIS_URL) return process.env.REDIS_URL;
  try {
    const txt = fs.readFileSync(path.join(process.cwd(), "..", "..", ".env"), "utf8");
    const m = txt.match(/^\s*(?:export\s+)?REDIS_URL\s*=\s*(.+?)\s*$/m);
    if (m) return m[1].trim().replace(/^["']|["']$/g, "");
  } catch {
    /* ignore */
  }
  return undefined;
}

const withTimeout = <T>(p: Promise<T>, ms = 1500): Promise<T> =>
  Promise.race([p, new Promise<T>((_, rej) => setTimeout(() => rej(new Error("redis timeout")), ms))]);

async function getClient(): Promise<MiniRedis | null> {
  if (disabled) return null;
  if (client) return client;
  if (connecting) return connecting;
  const url = redisUrl();
  if (!url) {
    disabled = true;
    return null;
  }
  connecting = (async () => {
    try {
      const c = createClient({ url, socket: { connectTimeout: 1500, reconnectStrategy: false } }) as unknown as MiniRedis;
      c.on("error", () => {}); // swallow — handled via try/catch
      await withTimeout(c.connect(), 1500);
      client = c;
      return c;
    } catch {
      disabled = true; // never retry / hang again this process
      return null;
    } finally {
      connecting = null;
    }
  })();
  return connecting;
}

export async function redisGet(wellId: string): Promise<Record<string, unknown> | null> {
  try {
    const c = await getClient();
    if (!c) return null;
    const v = await withTimeout(c.get(KEY(wellId)), 1500);
    return v ? (JSON.parse(v) as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export async function redisSet(wellId: string, dossier: unknown): Promise<void> {
  try {
    const c = await getClient();
    if (!c) return;
    await withTimeout(c.set(KEY(wellId), JSON.stringify(dossier), { EX: TTL }), 1500);
  } catch {
    /* ignore */
  }
}
