// Copies the committed datastore (data/processed/*.json) into public/data so the
// app can fetch it statically in dev, build, and on Vercel. Idempotent.
import { mkdirSync, copyFileSync, readdirSync, existsSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "..", "data", "processed");
const dest = join(here, "..", "public", "data");

// Archive-only files the web app never fetches — keep them out of deploys.
const SKIP = new Set(["candidates.scored.json"]);

if (!existsSync(src)) {
  console.warn(`[copy-data] source not found: ${src} (run the ingest pipeline first)`);
  process.exit(0);
}
mkdirSync(dest, { recursive: true });

let n = 0;
for (const f of readdirSync(src)) {
  if (SKIP.has(f)) continue;
  if (f.endsWith(".json") || f.endsWith(".geojson")) {
    copyFileSync(join(src, f), join(dest, f));
    n++;
  }
}

// Lazy-loaded per-well detail shards. Clear the dest first so a smaller run never
// leaves stale shards behind.
const detailSrc = join(src, "detail");
const detailDest = join(dest, "detail");
let shards = 0;
if (existsSync(detailDest)) rmSync(detailDest, { recursive: true, force: true });
if (existsSync(detailSrc)) {
  mkdirSync(detailDest, { recursive: true });
  for (const f of readdirSync(detailSrc)) {
    if (f.endsWith(".json")) {
      copyFileSync(join(detailSrc, f), join(detailDest, f));
      shards++;
    }
  }
}

console.log(`[copy-data] copied ${n} file(s) + ${shards} detail shard(s) -> public/data`);
