/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: "#080b10",
        panel: "#111821",
        panelLine: "#243244",
        thermal: "#ff5a1f",
        signal: "#36d399",
        alert: "#ff304f",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
