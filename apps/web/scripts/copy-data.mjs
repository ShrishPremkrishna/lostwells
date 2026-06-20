// Copies the committed datastore (data/processed/*.json) into public/data so the
// app can fetch it statically in dev, build, and on Vercel. Idempotent.
import { mkdirSync, copyFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "..", "data", "processed");
const dest = join(here, "..", "public", "data");

if (!existsSync(src)) {
  console.warn(`[copy-data] source not found: ${src} (run the ingest pipeline first)`);
  process.exit(0);
}
mkdirSync(dest, { recursive: true });
let n = 0;
for (const f of readdirSync(src)) {
  if (f.endsWith(".json") || f.endsWith(".geojson")) {
    copyFileSync(join(src, f), join(dest, f));
    n++;
  }
}
console.log(`[copy-data] copied ${n} file(s) -> public/data`);
