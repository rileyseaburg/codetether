export async function data() {
  const path = Bun.env.MODELS_DEV_API_JSON
  if (path) {
    const file = Bun.file(path)
    if (await file.exists()) {
      return await file.text()
    }
  }
  // At build time, fetch from codetether API to embed in binary
  const json = await Bun.file("/home/riley/A2A-Server-MCP/models.dev/packages/web/dist/_api.json").text()
  return json
}
