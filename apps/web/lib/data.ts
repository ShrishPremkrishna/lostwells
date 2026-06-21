import type {
  Candidate,
  CandidateLite,
  CaseFile,
  DocumentedWells,
  Dossier,
  KnowledgeEntry,
  Meta,
} from "./types";

const base = (f: string) => `/data/${f}`;

// Default "no-cache" = revalidate with the server (304 when unchanged → fast;
// fresh bytes when the datastore is re-generated). Small/mutable files (heroes,
// meta, dossiers) use "no-store". Avoids the stale-cache trap (removed heroes /
// stale scores persisting) while keeping reloads cheap.
async function getJSON<T>(file: string, cache: RequestCache = "no-cache"): Promise<T> {
  const res = await fetch(base(file), { cache });
  if (!res.ok) throw new Error(`failed to load ${file}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const loadDocumented = () =>
  getJSON<DocumentedWells>("wells.documented.json");

export const loadCandidates = () =>
  getJSON<CandidateLite[]>("candidates.web.json");

// Rank-bucketed detail shards (1000 wells/shard). Lazy-fetched + cached per shard
// when a well's DossierPanel opens; returns { well_id: <full record> }.
export const shardOf = (rank: number) => Math.floor((rank - 1) / 1000);

export const loadDetailShard = (shard: number) =>
  // Shard files are zero-padded to 2 digits (detail/00.json) by the pipeline.
  getJSON<Record<string, Candidate>>(`detail/${String(shard).padStart(2, "0")}.json`);

export const loadMeta = () => getJSON<Meta>("meta.json", "no-store");

export async function loadDossiers(): Promise<Record<string, Dossier>> {
  try {
    return await getJSON<Record<string, Dossier>>("dossiers.json", "no-store");
  } catch {
    return {};
  }
}

export async function loadCaseFiles(): Promise<Record<string, CaseFile>> {
  try {
    return await getJSON<Record<string, CaseFile>>("case_files.json", "no-store");
  } catch {
    return {};
  }
}

export async function loadKnowledge(): Promise<KnowledgeEntry[]> {
  try {
    return await getJSON<KnowledgeEntry[]>("knowledge.json", "no-store");
  } catch {
    return [];
  }
}

export async function loadHeroes(): Promise<Candidate[]> {
  try {
    return await getJSON<Candidate[]>("heroes.json", "no-store");
  } catch {
    return [];
  }
}
