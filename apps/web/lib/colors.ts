// Impact ramp (uidesign.md aesthetic): muted sage (low) -> olive -> forest ->
// danger red (highest human impact). Readable on the light field-survey shell.

type RGB = [number, number, number];

const STOPS: [number, RGB][] = [
  [0, [193, 205, 193]], // low — muted sage grey
  [45, [122, 174, 138]], // accent-soft
  [70, [74, 124, 89]], // accent
  [85, [46, 92, 62]], // accent-deep
  [100, [139, 58, 58]], // danger — highest impact
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

// Map marker colors. Names kept (TEAL/EMBER/DANGER) so existing imports work;
// values are the new light-theme palette.
export const TEAL: RGB = [110, 124, 140]; // documented backbone — muted slate
export const EMBER: RGB = [74, 124, 89]; // discovered wells — olive-green accent
export const DANGER: RGB = [139, 58, 58]; // hero wells — danger red

// Clearer aliases for new code.
export const DOCUMENTED = TEAL;
export const DISCOVERED = EMBER;
export const HERO = DANGER;

export const GROUP_COLORS: Record<string, string> = {
  human_exposure: "#4a7c59",
  equity: "#7aae8a",
};
