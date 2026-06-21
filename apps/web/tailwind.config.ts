import type { Config } from "tailwindcss";

/**
 * uidesign.md §2 — "topographic field survey meets intelligence dashboard."
 * Light shell, muted olive-to-forest green accent (never neon), grays derived
 * from #CFCFCF. Zero border-radius everywhere except pills (full) and badges (sm).
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#CFCFCF", // borders, dividers, inactive UI
        surface: {
          1: "#F5F5F5", // app shell background
          2: "#E8E8E8", // card / panel backgrounds
          3: "#CFCFCF", // input borders, subtle strokes
        },
        mid: "#A8A8A8", // secondary text, placeholders, disabled
        body: "#3D3D3D", // primary body text
        head: "#1A1A1A", // headlines, high-emphasis
        ink: "#0D0D0D", // near-black (map overlays at 85%)
        accent: {
          light: "#D4E8DA", // selected-row wash
          soft: "#7AAE8A", // tags, badges, secondary
          DEFAULT: "#4A7C59", // primary accent — buttons, pins, active
          deep: "#2E5C3E", // hover / pressed
          ink: "#1A3D29", // text on light-green
        },
        danger: "#8B3A3A", // high-risk wells, errors
        warning: "#8B6914", // medium risk
        success: "#2E5C3E",
        info: "#3A5F8B",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        none: "0",
        DEFAULT: "0", // zero-radius is the rule (uidesign.md §6)
        sm: "4px", // badges only
        full: "9999px", // pills only
      },
      boxShadow: {
        // The ONLY shadow in the UI: dossier panel left edge (uidesign.md §6).
        panel: "-4px 0 24px rgba(0,0,0,0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
