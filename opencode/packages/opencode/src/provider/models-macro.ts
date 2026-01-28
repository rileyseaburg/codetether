export async function data() {
  const path = Bun.env.MODELS_DEV_API_JSON
  if (path) {
    const file = Bun.file(path)
    if (await file.exists()) {
      return await file.text()
    }
  }
  // At build time, fetch from codetether API to embed in binary
  const json = await fetch("https://api.codetether.run/static/models/api.json").then((x) => x.text())
  return json
}
