import type { Candidate, DocumentedWells, Dossier, Meta } from "./types";

const base = (f: string) => `/data/${f}`;

async function getJSON<T>(file: string): Promise<T> {
  const res = await fetch(base(file), { cache: "force-cache" });
  if (!res.ok) throw new Error(`failed to load ${file}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const loadDocumented = () =>
  getJSON<DocumentedWells>("wells.documented.json");

export const loadCandidates = () =>
  getJSON<Candidate[]>("candidates.scored.json");

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
