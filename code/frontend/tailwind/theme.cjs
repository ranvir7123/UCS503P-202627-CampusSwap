// The one colour set every page uses: a calm, dark CampusSwap.
// Blue-grey surfaces, one brass accent (like a hostel key tag) for the main
// action and keyboard focus, and muted status colours.
module.exports = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: "#121A24", // page background
        sunken: "#0F161F", // inputs, code panels
        panel: "#1A2431", // cards
        raised: "#223042", // hover, selected, secondary buttons
        line: { DEFAULT: "#2E3D50", strong: "#3D4F66" },
        ink: { DEFAULT: "#E6EBF1", 2: "#B4C0CE", 3: "#8494A7" },
        brass: { DEFAULT: "#D4B06A", hover: "#E0C084", ink: "#1A1408" },
        info: "#8FAAE0", // open / in the pool
        ok: "#86C29E", // confirmed / approved
        bad: "#E39191", // declined / cancelled / errors
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"], // only for codes: tracking IDs, room numbers
      },
    },
  },
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/container-queries")],
};
