/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'arena-dark': '#05080f',
        'arena-card': 'rgba(13, 17, 23, 0.65)',
        'arena-border': 'rgba(255, 255, 255, 0.08)',
        'arena-blue': '#58a6ff',
        'arena-green': '#3fb950',
        'arena-red': '#f85149',
        'arena-text': '#e6edf3',
        'arena-muted': '#8b949e',
      },
      backgroundImage: {
        'arena-gradient': 'radial-gradient(at 0% 0%, rgba(18, 25, 36, 1) 0, transparent 50%), radial-gradient(at 100% 0%, rgba(13, 30, 56, 0.3) 0, transparent 50%)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'neon-blue': '0 0 24px rgba(88, 166, 255, 0.4)',
        'card': '0 16px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.05)',
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) forwards',
      },
      keyframes: {
        fadeIn: {
          'from': { opacity: '0', transform: 'translateY(10px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
