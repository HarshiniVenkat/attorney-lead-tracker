import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Single source of truth for the palette; components reference these
        // names rather than raw hex values.
        ink: {
          DEFAULT: "#0f172a",
          muted: "#475569",
          subtle: "#64748b",
        },
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f8fafc",
          sunken: "#f1f5f9",
        },
        line: {
          DEFAULT: "#e2e8f0",
          strong: "#cbd5e1",
        },
        brand: {
          DEFAULT: "#0f172a",
          accent: "#2563eb",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
