// Sequential impact ramp: deep teal-grey (low) -> amber -> ember -> danger red.
// One restrained accent system so the data, not the chrome, carries meaning.

type RGB = [number, number, number];

const STOPS: [number, RGB][] = [
  [0, [45, 90, 100]],
  [40, [70, 130, 128]],
  [55, [245, 166, 35]],
  [70, [255, 122, 24]],
  [85, [216, 64, 32]],
  [100, [239, 68, 68]],
];

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export function scoreRGB(score: number): RGB {
  const s = Math.max(0, Math.min(100, score));
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [t0, c0] = STOPS[i];
    const [t1, c1] = STOPS[i + 1];
    if (s >= t0 && s <= t1) {
      const t = (s - t0) / (t1 - t0 || 1);
      return [
        Math.round(lerp(c0[0], c1[0], t)),
        Math.round(lerp(c0[1], c1[1], t)),
        Math.round(lerp(c0[2], c1[2], t)),
      ];
    }
  }
  return STOPS[STOPS.length - 1][1];
}

export const scoreCSS = (score: number, alpha = 1) => {
  const [r, g, b] = scoreRGB(score);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

// Documented backbone: dim teal; candidates colored by score; heroes ember-red.
export const TEAL: RGB = [45, 212, 191];
export const EMBER: RGB = [255, 122, 24];
export const DANGER: RGB = [239, 68, 68];

export const GROUP_COLORS: Record<string, string> = {
  human_exposure: "#ff7a18",
  equity: "#f5a623",
  methane: "#9ca3af",
  fundability: "#2dd4bf",
};
