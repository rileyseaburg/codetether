import { createGrpcWebTransport } from '@connectrpc/connect-web'
import { createClient } from '@connectrpc/connect'
import { A2aService, VoiceService } from './gen/a2a_pb'

const GRPC_URL = process.env.NEXT_PUBLIC_GRPC_URL || 'http://localhost:50051'

/**
 * gRPC-Web transport for browser → codetether-agent gRPC server.
 * Uses HTTP/1.1 + gRPC-Web encoding via tonic-web on the server side.
 */
const transport = createGrpcWebTransport({
    baseUrl: GRPC_URL,
})

/**
 * Typed A2A gRPC client for the dashboard.
 * Supports all 10 RPCs including server-streaming (SendStreamingMessage, TaskSubscription).
 */
export const a2aClient = createClient(A2aService, transport)

/**
 * Typed Voice gRPC client for the dashboard.
 * Supports session management, voice listing, and streaming transcript events.
 */
export const voiceClient = createClient(VoiceService, transport)

/**
 * Create a transport with custom base URL (e.g. for multi-tenant or dynamic endpoints).
 */
export function createA2AClient(baseUrl: string) {
    const customTransport = createGrpcWebTransport({ baseUrl })
    return createClient(A2aService, customTransport)
}

/**
 * Create a voice client with custom base URL.
 */
export function createVoiceClient(baseUrl: string) {
    const customTransport = createGrpcWebTransport({ baseUrl })
    return createClient(VoiceService, customTransport)
}
