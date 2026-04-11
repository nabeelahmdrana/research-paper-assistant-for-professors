import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      borderColor: {
        DEFAULT: "hsl(var(--border))",
      },
      backgroundColor: {
        background: "hsl(var(--background))",
      },
      textColor: {
        foreground: "hsl(var(--foreground))",
      },
    },
  },
  plugins: [],
};

export default config;
