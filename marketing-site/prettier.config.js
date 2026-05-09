/** @type {import('prettier').Options} */
const plugins = []

try {
  require.resolve('prettier-plugin-tailwindcss')
  plugins.push('prettier-plugin-tailwindcss')
} catch {
  // CI may run before dependencies are installed.
}

module.exports = {
  singleQuote: true,
  semi: false,
  plugins,
  tailwindStylesheet: './src/styles/tailwind.css',
}
