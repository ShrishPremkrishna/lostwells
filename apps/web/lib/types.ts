// Shared types mirroring the committed datastore (data/processed/*.json).

export interface Methane {
  g_per_hr_point: number;
  g_per_hr_low: number;
  g_per_hr_high: number;
  t_ch4_per_yr_point: number;
  t_co2e_gwp100_point: number;
  t_co2e_gwp100_low: number;
  t_co2e_gwp100_high: number;
  t_co2e_gwp20_point: number;
  plugged: boolean;
  label: string;
  // §2B region × status × type differentiation metadata (all optional).
  region?: string;
  well_type?: string;
  status_known?: boolean;
  differentiated?: boolean;
  super_emitter?: boolean | null;
  super_emitter_dist_m?: number | null;
  super_emitter_rate_kg_hr?: number | null;
}

export interface PlugCost {
  plug_only_usd: number;
  reclamation_usd: number;
  point_usd: number;
  low_usd: number;
  high_usd: number;
  depth_known: boolean;
  is_gas: boolean;
  drivers: Record<string, number>;
}

export interface Carbon {
  creditable_tonnes: number;
  value_low_usd: number;
  value_point_usd: number;
  value_high_usd: number;
  self_funding_ratio_point: number;
  pencils_out: boolean;
  tier?: string;
  carbon_viable?: boolean;
  buffer_pool: number;
  crediting_period_years: number;
  label: string;
}

export interface Enrichment {
  population?: number | null;
  population_1mi?: number | null;
  daytime_population?: number | null;
  svi?: number | null;
  poverty_pct?: number | null;
  minority_pct?: number | null;
  ej?: number | null;
  eji_rank?: number | null;
  cejst_disadvantaged?: boolean | null;
  svi_socioeconomic?: number | null;
  svi_minority?: number | null;
  county?: string | null;
  tract_fips?: string | null;
  tract_geoid?: string | null;
  schools_within_1mi?: number | null;
  nearest_school?: string | null;
  nearest_school_m?: number | null;
  school_names?: string[];
  hospitals_within_5mi?: number | null;
  drinking_water_score?: number | null;
}

export interface Score {
  composite: number;
  breakdown: Record<string, number>;
  group_breakdown: Record<string, number>;
  normalized: Record<string, number | null>;
  present_metrics: string[];
  missing_metrics: string[];
  weights: Record<string, number>;
}

export interface Dossier {
  well_id: string;
  status: "complete" | "partial" | "cached" | "pending";
  operator_history?: string;
  bankruptcy_findings?: string;
  news_findings?: string;
  narrative?: string;
  sources?: { title: string; url: string }[];
  generated_by?: string;
  investigated_utc?: string;
}

// Lite subset shipped in candidates.web.json — everything the map, ranked list,
// hover tooltip, search, sort, and SwarmPanel need. The heavy detail (full score,
// methane, plug_cost, carbon, full enrichment) is lazy-loaded per shard for the
// DossierPanel. `Candidate` is a structural superset, so it stays assignable here.
export interface CandidateLite {
  well_id: string;
  rank: number;
  lat: number;
  lon: number;
  name: string;
  quad_name?: string;
  county_group?: string;
  state: string;
  source?: "lbnl" | "unet_2026";
  score: { composite: number };
  // Omitted when the well has no nearby population/schools (null fields stripped
  // from the slim payload), so optional — all reads are null-safe.
  enrichment?: Pick<
    Enrichment,
    | "population"
    | "population_1mi"
    | "schools_within_1mi"
    | "nearest_school_m"
    | "nearest_school"
    | "county"
  >;
  hero?: { title: string; place: string; confirmed: boolean };
}

export interface Candidate {
  well_id: string;
  layer: "candidate" | "hero";
  name: string;
  county_group?: string;
  state_abbr: string;
  state: string;
  quad_name?: string;
  quad_id?: string;
  quad_year?: string;
  quad_scale?: string;
  detection_index?: number;
  type_norm: string;
  status_norm: string;
  is_plugged: boolean;
  lat: number;
  lon: number;
  coord_source?: string;
  coord_precision?: string;
  nearest_doc_well_m?: number;
  methane: Methane;
  plug_cost: PlugCost;
  carbon: Carbon;
  enrichment: Enrichment;
  metrics: Record<string, number | null>;
  score: Score;
  rank: number;
  hero?: HeroMeta;
}

export interface HeroMeta {
  title: string;
  place: string;
  blurb: string;
  confirmed: boolean;
  pathway?: string;
  topo?: { year: string; label: string };
  citations?: { title: string; url: string }[];
}

export interface DocumentedWells {
  count: number;
  state_legend: string[];
  type_legend: string[];
  status_legend: string[];
  lon: number[];
  lat: number[];
  state_idx: number[];
  type_idx: number[];
  status_idx: number[];
}

export interface Discovery {
  definition: string;
  total_candidates: number;
  gt_100m: number;
  gt_500m: number;
  gt_1000m: number;
  median_nearest_documented_m: number;
  max_nearest_documented_m: number;
  by_source: Record<string, { candidates: number; gt_100m: number }>;
}

export interface Pathway {
  key: string;
  label: string;
  eligible: boolean;
  rationale: string;
  timeline: string;
  actor: string;
  confidence: string;
  priority: number;
}

export interface Actor {
  name?: string;
  party?: string | null;
  phone?: string | null;
  url?: string | null;
  email?: string | null;
  type?: string;
  chamber?: string;
  district?: string;
}

export interface Regulator {
  agency?: string;
  division?: string;
  program?: string;
  url?: string;
  phone?: string | null;
  email?: string | null;
}

export interface KnowledgeEntry {
  key: string;
  topic: string;
  value: string;
  source: string;
  well_id?: string | null;
}

export interface SurfaceOwner {
  owner?: string | null;
  owner_address?: string | null;
  physical_address?: string | null;
  acres?: number | null;
  parcel_id?: string | null;
  legal?: string | null;
  source_url?: string | null;
  state?: string | null;
  note?: string | null;
}

export interface CaseFile {
  well_id: string;
  rank: number;
  name?: string;
  state?: string;
  county?: string;
  evidence: Record<string, number | string | boolean | null>;
  pathways: Pathway[];
  actors: {
    responsible_regulator?: Regulator | null;
    can_fund?: Regulator | null;
    surface_owner?: SurfaceOwner | null;
    can_pressure: {
      us_senators: Actor[];
      us_representative: Actor | null;
      state_legislators: Actor[];
      ej_orgs: { org: string; scope: string; focus: string; url: string }[];
    };
    districts?: Record<string, string | null> | null;
    available: { federal: boolean; state_legislators: boolean; regulator: boolean };
  };
  story: { text: string; generated_by: string } | null;
}

export interface Meta {
  generated_utc: string;
  documented_count: number;
  candidate_count: number;
  documented_by_state: Record<string, number>;
  candidate_by_region: Record<string, number>;
  citations: Record<string, Record<string, unknown>>;
  discovery?: Discovery;
}

export const METRIC_LABELS: Record<string, string> = {
  population: "Population nearby",
  schools: "Schools within 1 mi",
  hospitals: "Hospitals / sensitive sites",
  drinking_water: "Drinking-water proximity",
  svi: "Social Vulnerability",
  ej: "Environmental-justice burden",
  methane: "Methane (modeled, region/type)",
  fundability_cost: "Low plug cost (tractable)",
  program_match: "Funding-program match",
};

export const GROUP_LABELS: Record<string, string> = {
  human_exposure: "Human exposure",
  equity: "Equity",
  methane: "Methane",
  fundability: "Fundability",
};
