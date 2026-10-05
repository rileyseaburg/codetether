'use client'

import { useState, useRef, useCallback } from 'react'

const VOICE_API_URL =
    process.env.NEXT_PUBLIC_VOICE_API_URL || 'https://voice.quantum-forge.io'
const DEFAULT_VOICE_ID = '960f89fc' // Riley

interface UseVoiceOptions {
    voiceId?: string
    language?: string
    /** Called when speech starts playing */
    onStart?: () => void
    /** Called when speech finishes playing */
    onEnd?: () => void
    /** Called on error */
    onError?: (error: string) => void
}

interface UseVoiceReturn {
    /** Speak the given text using the cloned voice */
    speak: (text: string) => Promise<void>
    /** Stop any currently playing audio */
    stop: () => void
    /** Whether audio is currently playing */
    isPlaying: boolean
    /** Whether audio is loading from the API */
    isLoading: boolean
    /** Error message if the last request failed */
    error: string | null
}

/**
 * React hook for text-to-speech using the Qwen TTS Voice Cloning API.
 *
 * Uses a cloned voice (default: Riley) to speak text aloud.
 * Audio is generated server-side via Qwen3-TTS and streamed to the browser.
 *
 * @example
 * ```tsx
 * const { speak, stop, isPlaying, isLoading } = useVoice()
 * <button onClick={() => isPlaying ? stop() : speak('Hello world')}>
 *   {isPlaying ? 'Stop' : isLoading ? 'Loading...' : 'Read Aloud'}
 * </button>
 * ```
 */
export function useVoice(options: UseVoiceOptions = {}): UseVoiceReturn {
    const {
        voiceId = DEFAULT_VOICE_ID,
        language = 'english',
        onStart,
        onEnd,
        onError,
    } = options

    const [isPlaying, setIsPlaying] = useState(false)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const audioRef = useRef<HTMLAudioElement | null>(null)
    const abortRef = useRef<AbortController | null>(null)

    const stop = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause()
            audioRef.current.src = ''
            audioRef.current = null
        }
        if (abortRef.current) {
            abortRef.current.abort()
            abortRef.current = null
        }
        setIsPlaying(false)
        setIsLoading(false)
    }, [])

    const speak = useCallback(
        async (text: string) => {
            // Stop any existing playback
            stop()

            if (!text.trim()) return

            setIsLoading(true)
            setError(null)

            const controller = new AbortController()
            abortRef.current = controller

            try {
                const formData = new FormData()
                formData.append('text', text)
                formData.append('language', language)

                const response = await fetch(
                    `${VOICE_API_URL}/voices/${voiceId}/speak`,
                    {
                        method: 'POST',
                        body: formData,
                        signal: controller.signal,
                    },
                )

                if (!response.ok) {
                    const errorText = await response.text()
                    throw new Error(`Voice API error ${response.status}: ${errorText}`)
                }

                const blob = await response.blob()
                const url = URL.createObjectURL(blob)
                const audio = new Audio(url)
                audioRef.current = audio

                audio.onplay = () => {
                    setIsPlaying(true)
                    setIsLoading(false)
                    onStart?.()
                }

                audio.onended = () => {
                    setIsPlaying(false)
                    URL.revokeObjectURL(url)
                    audioRef.current = null
                    onEnd?.()
                }

                audio.onerror = () => {
                    setIsPlaying(false)
                    setIsLoading(false)
                    URL.revokeObjectURL(url)
                    audioRef.current = null
                    const msg = 'Audio playback failed'
                    setError(msg)
                    onError?.(msg)
                }

                await audio.play()
            } catch (err) {
                if (err instanceof DOMException && err.name === 'AbortError') return
                const msg = err instanceof Error ? err.message : 'Voice synthesis failed'
                setError(msg)
                setIsLoading(false)
                onError?.(msg)
            }
        },
        [voiceId, language, stop, onStart, onEnd, onError],
    )

    return { speak, stop, isPlaying, isLoading, error }
}
