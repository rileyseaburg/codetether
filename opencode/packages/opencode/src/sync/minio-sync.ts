/**
 * MinIO Sync Module for OpenCode
 *
 * Provides continuous file synchronization to MinIO object storage.
 * Designed for distributed workers that need to sync workspace files
 * (code, docs, images, any files) alongside git commits.
 *
 * Uses S3-compatible HTTP API - no minio npm package required.
 *
 * Environment Variables:
 * - MINIO_ENDPOINT: MinIO server URL (e.g., "minio.example.com:9000")
 * - MINIO_BUCKET: Bucket name for codebases
 * - MINIO_ACCESS_KEY: Access key ID
 * - MINIO_SECRET_KEY: Secret access key
 * - MINIO_SECURE: "true" for HTTPS, "false" for HTTP (default: "true")
 */

import { Log } from "../util/log"
import { createHmac, createHash } from "crypto"
import path from "path"
import fs from "fs/promises"

const log = Log.create({ service: "minio-sync" })

export namespace MinioSync {
  interface MinioConfig {
    endpoint: string
    bucket: string
    accessKey: string
    secretKey: string
    secure: boolean
  }

  let config: MinioConfig | null = null
  let syncInterval: ReturnType<typeof setInterval> | null = null
  let isSyncing = false

  /**
   * Initialize MinIO client from environment variables or explicit config
   */
  export function init(explicitConfig?: Partial<MinioConfig>): void {
    const endpoint = explicitConfig?.endpoint || process.env.MINIO_ENDPOINT
    const bucket = explicitConfig?.bucket || process.env.MINIO_BUCKET
    const accessKey = explicitConfig?.accessKey || process.env.MINIO_ACCESS_KEY
    const secretKey = explicitConfig?.secretKey || process.env.MINIO_SECRET_KEY
    const secure = explicitConfig?.secure ?? process.env.MINIO_SECURE !== "false"

    if (!endpoint || !bucket || !accessKey || !secretKey) {
      throw new Error(
        "MinIO sync requires MINIO_ENDPOINT, MINIO_BUCKET, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY"
      )
    }

    config = { endpoint, bucket, accessKey, secretKey, secure }
    log.info("MinIO sync initialized", { endpoint, bucket, secure })
  }

  /**
   * Check if MinIO sync is configured and available
   */
  export function isAvailable(): boolean {
    return !!(
      process.env.MINIO_ENDPOINT &&
      process.env.MINIO_BUCKET &&
      process.env.MINIO_ACCESS_KEY &&
      process.env.MINIO_SECRET_KEY
    )
  }

  /**
   * Download a codebase tarball from MinIO and extract to target directory
   */
  export async function downloadCodebase(
    codebaseId: string,
    targetDir: string
  ): Promise<{ success: boolean; filesExtracted: number }> {
    if (!config) throw new Error("MinIO not initialized. Call init() first.")

    const objectKey = `codebases/${codebaseId}/codebase.tar.gz`
    const timer = log.time("Download codebase", { codebaseId, targetDir })

    try {
      // Ensure target directory exists
      await fs.mkdir(targetDir, { recursive: true })

      // Download the tarball
      const response = await s3Request("GET", objectKey)
      if (!response.ok) {
        if (response.status === 404) {
          log.info("Codebase not found in MinIO, starting fresh", { codebaseId })
          return { success: true, filesExtracted: 0 }
        }
        throw new Error(`Failed to download: ${response.status} ${response.statusText}`)
      }

      // Stream to temp file then extract
      const tarballPath = path.join(targetDir, ".minio-download.tar.gz")
      const arrayBuffer = await response.arrayBuffer()
      await Bun.write(tarballPath, arrayBuffer)

      // Extract using tar
      const proc = Bun.spawn(["tar", "-xzf", tarballPath, "-C", targetDir], {
        stdout: "pipe",
        stderr: "pipe",
      })
      const exitCode = await proc.exited
      
      // Clean up temp file
      await fs.unlink(tarballPath).catch(() => {})

      if (exitCode !== 0) {
        const stderr = await new Response(proc.stderr).text()
        throw new Error(`tar extraction failed: ${stderr}`)
      }

      // Count extracted files
      const filesExtracted = await countFiles(targetDir)
      log.info("Codebase downloaded and extracted", { codebaseId, filesExtracted })
      timer.stop()

      return { success: true, filesExtracted }
    } catch (error) {
      log.error("Failed to download codebase", {
        codebaseId,
        error: error instanceof Error ? error.message : String(error),
      })
      timer.stop()
      throw error
    }
  }

  /**
   * Create a tarball of the source directory and upload to MinIO
   */
  export async function uploadCodebase(
    codebaseId: string,
    sourceDir: string
  ): Promise<{ success: boolean; bytesUploaded: number }> {
    if (!config) throw new Error("MinIO not initialized. Call init() first.")

    const objectKey = `codebases/${codebaseId}/codebase.tar.gz`
    const timer = log.time("Upload codebase", { codebaseId, sourceDir })

    try {
      // Create tarball in temp location
      const tarballPath = path.join(sourceDir, ".minio-upload.tar.gz")

      // Create tar excluding common unneeded files
      const excludeArgs = [
        "--exclude=.git",
        "--exclude=node_modules",
        "--exclude=.minio-upload.tar.gz",
        "--exclude=.minio-download.tar.gz",
        "--exclude=__pycache__",
        "--exclude=.pytest_cache",
        "--exclude=.venv",
        "--exclude=venv",
        "--exclude=dist",
        "--exclude=build",
        "--exclude=*.pyc",
        "--exclude=.DS_Store",
      ]

      const proc = Bun.spawn(
        ["tar", "-czf", tarballPath, ...excludeArgs, "-C", sourceDir, "."],
        { stdout: "pipe", stderr: "pipe" }
      )
      const exitCode = await proc.exited

      if (exitCode !== 0) {
        const stderr = await new Response(proc.stderr).text()
        throw new Error(`tar creation failed: ${stderr}`)
      }

      // Read and upload
      const tarball = Bun.file(tarballPath)
      const buffer = await tarball.arrayBuffer()
      const bytesUploaded = buffer.byteLength

      await s3Request("PUT", objectKey, new Uint8Array(buffer), {
        "Content-Type": "application/gzip",
      })

      // Clean up temp file
      await fs.unlink(tarballPath).catch(() => {})

      log.info("Codebase uploaded", { codebaseId, bytesUploaded })
      timer.stop()

      return { success: true, bytesUploaded }
    } catch (error) {
      log.error("Failed to upload codebase", {
        codebaseId,
        error: error instanceof Error ? error.message : String(error),
      })
      timer.stop()
      throw error
    }
  }

  /**
   * Perform an immediate sync (upload) of the codebase
   */
  export async function syncNow(
    codebaseId: string,
    sourceDir: string
  ): Promise<{ success: boolean; bytesUploaded: number }> {
    if (isSyncing) {
      log.warn("Sync already in progress, skipping", { codebaseId })
      return { success: false, bytesUploaded: 0 }
    }

    isSyncing = true
    try {
      return await retryWithBackoff(
        () => uploadCodebase(codebaseId, sourceDir),
        3,
        1000
      )
    } finally {
      isSyncing = false
    }
  }

  /**
   * Start a background sync loop that uploads periodically
   */
  export function startSyncLoop(
    codebaseId: string,
    sourceDir: string,
    intervalMs: number = 30000
  ): void {
    if (syncInterval) {
      log.warn("Sync loop already running, stopping previous one")
      stopSyncLoop()
    }

    log.info("Starting sync loop", { codebaseId, intervalMs })

    // Initial sync
    syncNow(codebaseId, sourceDir).catch((err) => {
      log.error("Initial sync failed", { error: err.message })
    })

    // Periodic sync
    syncInterval = setInterval(async () => {
      try {
        await syncNow(codebaseId, sourceDir)
      } catch (error) {
        log.error("Periodic sync failed", {
          codebaseId,
          error: error instanceof Error ? error.message : String(error),
        })
      }
    }, intervalMs)

    // Handle process exit gracefully
    const cleanup = () => {
      log.info("Process exit detected, performing final sync")
      stopSyncLoop()
      syncNow(codebaseId, sourceDir)
        .catch((err) => log.error("Final sync failed", { error: err.message }))
        .finally(() => process.exit(0))
    }

    process.once("SIGINT", cleanup)
    process.once("SIGTERM", cleanup)
  }

  /**
   * Stop the background sync loop
   */
  export function stopSyncLoop(): void {
    if (syncInterval) {
      clearInterval(syncInterval)
      syncInterval = null
      log.info("Sync loop stopped")
    }
  }

  /**
   * Upload a single file to MinIO (for incremental syncs)
   */
  export async function uploadFile(
    codebaseId: string,
    filePath: string,
    localPath: string
  ): Promise<void> {
    if (!config) throw new Error("MinIO not initialized. Call init() first.")

    const objectKey = `codebases/${codebaseId}/files/${filePath}`
    const file = Bun.file(localPath)
    const buffer = await file.arrayBuffer()

    await s3Request("PUT", objectKey, new Uint8Array(buffer), {
      "Content-Type": getMimeType(filePath),
    })

    log.debug("File uploaded", { codebaseId, filePath, bytes: buffer.byteLength })
  }

  /**
   * Download a single file from MinIO
   */
  export async function downloadFile(
    codebaseId: string,
    filePath: string,
    localPath: string
  ): Promise<void> {
    if (!config) throw new Error("MinIO not initialized. Call init() first.")

    const objectKey = `codebases/${codebaseId}/files/${filePath}`
    const response = await s3Request("GET", objectKey)

    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.status}`)
    }

    const buffer = await response.arrayBuffer()
    await fs.mkdir(path.dirname(localPath), { recursive: true })
    await Bun.write(localPath, buffer)

    log.debug("File downloaded", { codebaseId, filePath, bytes: buffer.byteLength })
  }

  /**
   * List files in a codebase prefix
   */
  export async function listFiles(
    codebaseId: string,
    prefix: string = ""
  ): Promise<string[]> {
    if (!config) throw new Error("MinIO not initialized. Call init() first.")

    const objectPrefix = `codebases/${codebaseId}/files/${prefix}`
    const response = await s3Request(
      "GET",
      "",
      undefined,
      {},
      `?list-type=2&prefix=${encodeURIComponent(objectPrefix)}`
    )

    if (!response.ok) {
      throw new Error(`Failed to list files: ${response.status}`)
    }

    const xml = await response.text()
    // Simple XML parsing for S3 ListObjectsV2 response
    const keys: string[] = []
    const keyMatches = xml.matchAll(/<Key>([^<]+)<\/Key>/g)
    for (const match of keyMatches) {
      const key = match[1].replace(`codebases/${codebaseId}/files/`, "")
      if (key) keys.push(key)
    }

    return keys
  }

  // ============= Internal Helpers =============

  /**
   * Make an S3-compatible request to MinIO
   */
  async function s3Request(
    method: string,
    objectKey: string,
    body?: Uint8Array,
    extraHeaders: Record<string, string> = {},
    queryString: string = ""
  ): Promise<Response> {
    if (!config) throw new Error("MinIO not initialized")

    const protocol = config.secure ? "https" : "http"
    const host = config.endpoint
    const date = new Date().toUTCString()
    const contentMd5 = body ? createHash("md5").update(body).digest("base64") : ""
    const contentType = extraHeaders["Content-Type"] || ""

    // Build path
    const path = `/${config.bucket}/${objectKey}`.replace(/\/+/g, "/")

    // AWS Signature Version 2 (simpler, MinIO supports it)
    const stringToSign = [
      method,
      contentMd5,
      contentType,
      date,
      path,
    ].join("\n")

    const signature = createHmac("sha1", config.secretKey)
      .update(stringToSign)
      .digest("base64")

    const headers: Record<string, string> = {
      Host: host,
      Date: date,
      Authorization: `AWS ${config.accessKey}:${signature}`,
      ...extraHeaders,
    }

    if (contentMd5) headers["Content-MD5"] = contentMd5

    const url = `${protocol}://${host}${path}${queryString}`

    return fetch(url, {
      method,
      headers,
      body: body ? Buffer.from(body) : undefined,
    })
  }

  /**
   * Retry a function with exponential backoff
   */
  async function retryWithBackoff<T>(
    fn: () => Promise<T>,
    maxRetries: number,
    initialDelayMs: number
  ): Promise<T> {
    let lastError: Error | undefined
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        return await fn()
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error))
        if (attempt < maxRetries - 1) {
          const delay = initialDelayMs * Math.pow(2, attempt)
          log.warn("Retrying after error", {
            attempt: attempt + 1,
            maxRetries,
            delay,
            error: lastError.message,
          })
          await sleep(delay)
        }
      }
    }
    throw lastError
  }

  /**
   * Sleep for a given number of milliseconds
   */
  function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  /**
   * Count files in a directory recursively
   */
  async function countFiles(dir: string): Promise<number> {
    let count = 0
    const glob = new Bun.Glob("**/*")
    for await (const _file of glob.scan({ cwd: dir, onlyFiles: true })) {
      count++
    }
    return count
  }

  /**
   * Get MIME type from file extension
   */
  function getMimeType(filePath: string): string {
    const ext = path.extname(filePath).toLowerCase()
    const mimeTypes: Record<string, string> = {
      // Documents
      ".txt": "text/plain",
      ".md": "text/markdown",
      ".json": "application/json",
      ".xml": "application/xml",
      ".yaml": "application/x-yaml",
      ".yml": "application/x-yaml",
      ".html": "text/html",
      ".css": "text/css",
      ".csv": "text/csv",
      ".pdf": "application/pdf",
      ".doc": "application/msword",
      ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      
      // Code
      ".js": "application/javascript",
      ".ts": "application/typescript",
      ".jsx": "application/javascript",
      ".tsx": "application/typescript",
      ".py": "text/x-python",
      ".rb": "text/x-ruby",
      ".go": "text/x-go",
      ".rs": "text/x-rust",
      ".java": "text/x-java",
      ".c": "text/x-c",
      ".cpp": "text/x-c++",
      ".h": "text/x-c",
      ".sh": "application/x-sh",
      
      // Images
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".gif": "image/gif",
      ".svg": "image/svg+xml",
      ".webp": "image/webp",
      ".ico": "image/x-icon",
      
      // Archives
      ".zip": "application/zip",
      ".tar": "application/x-tar",
      ".gz": "application/gzip",
      ".tar.gz": "application/gzip",
      
      // Default
      "": "application/octet-stream",
    }

    return mimeTypes[ext] || "application/octet-stream"
  }
}
