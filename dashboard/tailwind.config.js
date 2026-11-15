/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Paleta validada (dataviz skill) + figuras de P2
        surface: "#fcfcfb",
        plane: "#f9f9f7",
        ink: {
          DEFAULT: "#0b0b0b",
          secondary: "#52514e",
          muted: "#898781",
        },
        hair: "#e1e0d9",
        axis: "#c3c2b7",
        blue: "#2a78d6",
        orange: "#eb6834",
        aqua: "#1baf7a",
        yellow: "#eda100",
        magenta: "#e87ba4",
        violet: "#6250d6",
        red: "#e34948",
        good: "#0ca30c",
        warning: "#fab219",
        critical: "#d03b3b",
        upc: "#007bc0", // blau del logo UPC (marca + diners)
        co2: "#1f8f56", // verd = CO₂
        solar: "#f5a623", // ambre = solar
        money: "#007bc0", // blau UPC = diners
        night: "#0e1b2b", // barra lateral fosca
        night2: "#132538",
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', '"Segoe UI"', "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.05)",
        soft: "0 1px 2px rgba(16,24,40,0.04), 0 14px 30px -16px rgba(16,24,40,0.18)",
        lift: "0 2px 6px rgba(16,24,40,0.06), 0 22px 44px -18px rgba(16,24,40,0.26)",
      },
      borderRadius: {
        "2xl": "1.1rem",
        "3xl": "1.5rem",
      },
    },
  },
  plugins: [],
};
