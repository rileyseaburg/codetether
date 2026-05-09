const plugins = []

try {
  require.resolve('prettier-plugin-tailwindcss')
  plugins.push('prettier-plugin-tailwindcss')
} catch {
  // CI may run before dependencies are installed.
}

/** @type {import('prettier').Options} */
const config = {
  singleQuote: true,
  semi: false,
  plugins,
}

if (plugins.length > 0) {
  config.tailwindStylesheet = './src/styles/tailwind.css'
}

module.exports = config
