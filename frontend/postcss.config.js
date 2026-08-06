// PostCSS pipeline used by Vite's CSS processing step: runs Tailwind's directives
// (@tailwind base/components/utilities in index.css) through the Tailwind plugin, then
// autoprefixer adds vendor-prefixed properties for broader browser compatibility.
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
