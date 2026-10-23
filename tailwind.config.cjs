// Tailwind build for the public site (replaces the cdn.tailwindcss.com play script).
// Brand colours come from static/brand/tokens.css so <html data-brand> switches them.
const brand = name => `rgb(var(--brand-${name}-rgb) / <alpha-value>)`;

module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: brand('primary'),
          hover: brand('primary-hover'),
          deep: brand('primary-deep'),
          accent: brand('accent'),
          soft: brand('on-primary-soft'),
          tint: 'var(--brand-tint)',
          border: 'var(--brand-border)',
        },
      },
      fontFamily: {
        sans: ['var(--brand-font)'],
      },
    },
  },
};
