import type { Config } from 'tailwindcss'

export default {
  content: [
    './index.html',
    './src/**/*.{vue,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Page background
        page: '#0d1117',
        // Card/panel background
        card: '#161b22',
        // Divider/border
        divider: '#21262d',
        // Text colors
        ink: {
          DEFAULT: '#b0b8c4',
          muted: '#6e7681',
        },
        // Accent - steel blue-gray
        accent: {
          DEFAULT: '#7b8c9e',
          hover: '#8f9fae',
        },
        // Functional
        success: '#5c7c6e',
        danger: '#d73a49',
        neutral: '#6e7b8c',
      },
      fontFamily: {
        heading: ['EB Garamond', 'Georgia', 'serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        'display': ['2.5rem', { lineHeight: '1.15', fontWeight: '700', letterSpacing: '-0.02em' }],
        'display-md': ['1.75rem', { lineHeight: '1.2', fontWeight: '700', letterSpacing: '-0.01em' }],
      },
      borderRadius: {
        'card': '0.5rem',
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.3)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.4)',
        'navbar': '0 1px 2px 0 rgb(0 0 0 / 0.3)',
      },
      maxWidth: {
        'content': '72rem',
      },
      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'slide-up': 'slideUp 200ms ease-out',
        'skeleton': 'skeleton 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        skeleton: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config
