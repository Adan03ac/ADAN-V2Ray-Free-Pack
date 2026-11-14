import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#080A0B",
          900: "#0B0E0F",
          850: "#111416",
          800: "#171B1D",
          700: "#1E2325",
          600: "#28302F",
        },
        neon: {
          DEFAULT: "#9DFF00",
          300: "#C8FF6B",
          400: "#AFEF1F",
          500: "#9DFF00",
          600: "#7ACC00",
        },
        violet: {
          DEFAULT: "#8B5CF6",
          400: "#A78BFA",
          600: "#7C3AED",
        },
        chalk: { 100: "#F3F5F4", 200: "#DCE2DF", 300: "#C9CFCC", 400: "#919B98", 500: "#6E7875", 600: "#535C59" },
        signal: {
          success: "#34D399",
          warning: "#FBBF24",
          danger: "#F87171",
          info: "#60A5FA",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        "2xl": "18px",
        "3xl": "24px",
        "4xl": "32px",
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 24px 60px -40px rgba(0,0,0,0.9)",
        neon: "0 0 0 1px rgba(157,255,0,0.18), 0 18px 50px -28px rgba(157,255,0,0.35)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-ring": {
          "0%,100%": { opacity: "0.35" },
          "50%": { opacity: "0.75" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out both",
        shimmer: "shimmer 1.8s infinite",
        "pulse-ring": "pulse-ring 3.2s ease-in-out infinite",
      },
      backgroundImage: {
        "grid-faint":
          "linear-gradient(to right, rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.025) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};

export default config;
