// Only the California Burrito brand colors are available to utility classes.
// CSS custom properties in src/style.css are the runtime source of truth.
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      'cb-red': '#E31F2D',
      'cb-red-deep': '#B8231A',
      'cb-green': '#2F4F3A',
      'cb-cream': '#FFECCD',
      'cb-white': '#FFFFFF',
      transparent: 'transparent',
      current: 'currentColor',
    },
    fontFamily: { sans: ['Gabarito', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
    extend: {},
  },
  corePlugins: { preflight: false },
};
