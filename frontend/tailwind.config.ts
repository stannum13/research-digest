import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ["var(--font-serif)"],
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      colors: {
        paper: {
          base: "var(--bg-base)",
          card: "var(--bg-card)",
          wash: "var(--bg-wash)",
          soft: "var(--bg-soft)",
        },
        ink: {
          DEFAULT: "var(--text-ink)",
          note: "var(--text-note)",
          faint: "var(--text-faint)",
        },
        accent: {
          clay: "var(--accent-clay)",
          sage: "var(--accent-sage)",
          ochre: "var(--accent-ochre)",
          lavender: "var(--accent-lavender)",
          rose: "var(--accent-rose)",
          plum: "var(--accent-plum)",
        },
      },
      boxShadow: {
        card: "var(--shadow-card)",
        hover: "var(--shadow-hover)",
      },
      transitionTimingFunction: {
        notebook: "var(--ease-out)",
      },
    },
  },
  plugins: [],
} satisfies Config;
