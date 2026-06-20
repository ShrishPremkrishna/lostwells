export const fmtInt = (n?: number | null) =>
  n == null ? "—" : Math.round(n).toLocaleString("en-US");

export const fmtUSD = (n?: number | null) => {
  if (n == null) return "—";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${Math.round(n)}`;
};

export const fmtPct = (n?: number | null, digits = 0) =>
  n == null ? "—" : `${(n * 100).toFixed(digits)}%`;

export const fmtMiles = (meters?: number | null) => {
  if (meters == null) return "—";
  const mi = meters / 1609.34;
  if (mi < 0.1) return `${Math.round(meters)} m`;
  return `${mi.toFixed(mi < 1 ? 2 : 1)} mi`;
};

export const fmtTonnes = (n?: number | null, digits = 2) =>
  n == null ? "—" : `${n.toFixed(digits)} t`;

export const titleCase = (s?: string | null) =>
  !s ? "" : s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
