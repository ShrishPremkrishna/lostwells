import type { Candidate, CandidateLite, DocumentedWells, Dossier, Meta } from "./types";

const base = (f: string) => `/data/${f}`;

async function getJSON<T>(file: string): Promise<T> {
  const res = await fetch(base(file), { cache: "force-cache" });
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
  getJSON<Record<string, Candidate>>(`detail/${shard}.json`);

export const loadMeta = () => getJSON<Meta>("meta.json");

export async function loadDossiers(): Promise<Record<string, Dossier>> {
  try {
    return await getJSON<Record<string, Dossier>>("dossiers.json");
  } catch {
    return {};
  }
}

export async function loadHeroes(): Promise<Candidate[]> {
  try {
    return await getJSON<Candidate[]>("heroes.json");
  } catch {
    return [];
  }
}
