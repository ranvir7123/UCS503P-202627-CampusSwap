// Theme copied from reference 2 (student dashboard).
// One change: the reference set `violet` to a single colour, which silently
// removes Tailwind's violet-50..900 shades (violet-600 avatars rendered white).
// We keep the reference violet as the DEFAULT and restore the shades.
const colors = require("tailwindcss/colors");

module.exports = {
  content: ["./public/dashboard.html", "./public/js/dashboard.js", "./public/js/ring.js", "./public/js/ui.js", "./public/js/nav.js"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary": "#FF385C",
        "primary-hover": "#E00B41",
        "primary-light": "#FFF0F2",
        "primary-subtle": "#FFE4E8",
        "marigold": "#FFB300",
        "marigold-light": "#FFF8E1",
        "marigold-subtle": "#FFF4CE",
        "violet": { ...colors.violet, DEFAULT: "#7C3AED" },
        "violet-light": "#F5F3FF",
        "violet-subtle": "#EDE9FE",
        "emerald-custom": "#10B981",
        "emerald-light": "#ECFDF5",
        "surface-card": "#FFFFFF",
        "surface-bg": "#F8FAFC",
        "border-subtle": "#E2E8F0",
        "border-strong": "#CBD5E1",
        "text-primary": "#0F172A",
        "text-secondary": "#475569",
        "text-tertiary": "#94A3B8",
        "dorm-badge": "#334155",
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      keyframes: {
        flowDash: { "0%": { strokeDashoffset: "48" }, "100%": { strokeDashoffset: "0" } },
        flowDashReverse: { "0%": { strokeDashoffset: "0" }, "100%": { strokeDashoffset: "48" } },
        radarPulse: {
          "0%": { transform: "scale(0.95)", opacity: "0.8" },
          "70%": { transform: "scale(1.4)", opacity: "0" },
          "100%": { transform: "scale(1.5)", opacity: "0" },
        },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        popBounce: { "0%": { transform: "scale(0.9)" }, "50%": { transform: "scale(1.08)" }, "100%": { transform: "scale(1)" } },
        glowSubtle: {
          "0%, 100%": { boxShadow: "0 0 15px -3px rgba(255, 56, 92, 0.35), 0 0 6px -2px rgba(255, 56, 92, 0.2)" },
          "50%": { boxShadow: "0 0 25px 2px rgba(255, 56, 92, 0.55), 0 0 10px 0px rgba(255, 56, 92, 0.3)" },
        },
      },
      animation: {
        "flow-ring": "flowDash 1.8s linear infinite",
        "flow-ring-fast": "flowDash 1.2s linear infinite",
        "radar-1": "radarPulse 2.4s cubic-bezier(0.2, 0.6, 0.35, 1) infinite",
        "radar-2": "radarPulse 2.4s cubic-bezier(0.2, 0.6, 0.35, 1) infinite 0.8s",
        "shimmer-bar": "shimmer 2.2s infinite linear",
        "button-shimmer": "shimmer 3s infinite linear",
        "glow-pulse": "glowSubtle 2.5s ease-in-out infinite",
        "pop": "popBounce 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)",
      },
    },
  },
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/container-queries")],
};
