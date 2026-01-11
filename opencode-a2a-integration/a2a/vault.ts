import { Log } from "../util/log"

export namespace Vault {
  const log = Log.create({ service: "vault" })

  export interface Config {
    address: string
    token: string
    namespace?: string
  }

  function defaults(): Config {
    return {
      address: process.env.VAULT_ADDR ?? "http://localhost:8200",
      token: process.env.VAULT_TOKEN ?? "",
    }
  }

  function headers(config: Config): Record<string, string> {
    const result: Record<string, string> = {
      "X-Vault-Token": config.token,
    }
    if (config.namespace) {
      result["X-Vault-Namespace"] = config.namespace
    }
    return result
  }

  export async function getSecret(config: Config, path: string): Promise<Record<string, string> | null> {
    const url = `${config.address}/v1/secret/data/${path}`
    log.info("fetching secret", { path })

    const response = await fetch(url, {
      headers: headers(config),
    })

    if (response.status === 404) {
      log.info("secret not found", { path })
      return null
    }

    if (!response.ok) {
      log.error("failed to fetch secret", { path, status: response.status })
      return null
    }

    const body = (await response.json()) as { data?: { data?: Record<string, string> } }
    const data = body.data?.data
    if (!data) {
      log.error("unexpected response structure", { path })
      return null
    }

    log.info("secret fetched", { path })
    return data
  }

  export async function getSendGridKey(config?: Partial<Config>): Promise<string | null> {
    const merged = { ...defaults(), ...config }
    const secret = await getSecret(merged, "sendgrid")
    if (!secret) return null
    return secret.api_key ?? secret.apiKey ?? secret.API_KEY ?? null
  }
}
