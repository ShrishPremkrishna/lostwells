import type { Config } from "tailwindcss";

/**
 * Restrained environmental-investigation palette (spec §5.3):
 * near-black "ink" base, ONE urgent ember accent for high-impact wells, a cool
 * teal for documented wells, and danger red reserved for confirmed exposure.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#06080b",
          900: "#0a0d12",
          850: "#0f131a",
          800: "#141922",
          700: "#1d2430",
          600: "#2a3340",
          500: "#3b4654",
          400: "#5a6675",
          300: "#8b97a6",
          200: "#b9c2cd",
        },
        ember: {
          DEFAULT: "#ff7a18",
          soft: "#f5a623",
          deep: "#c2410c",
        },
        teal: {
          DEFAULT: "#2dd4bf",
          deep: "#0f766e",
        },
        danger: "#ef4444",
        paper: "#f4f1ea",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      fontFeatureSettings: {
        nums: '"tnum" 1',
      },
      boxShadow: {
        panel: "0 24px 64px -24px rgba(0,0,0,0.8)",
        glow: "0 0 24px -4px rgba(255,122,24,0.5)",
      },
      keyframes: {
        pulsering: {
          "0%": { transform: "scale(0.6)", opacity: "0.7" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        pulsering: "pulsering 2s ease-out infinite",
        shimmer: "shimmer 1.5s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
