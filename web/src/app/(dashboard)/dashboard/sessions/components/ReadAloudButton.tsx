'use client'

import { useVoice } from '@/hooks/useVoice'

interface ReadAloudButtonProps {
    text: string
    className?: string
}

export function ReadAloudButton({ text, className = '' }: ReadAloudButtonProps) {
    const { speak, stop, isPlaying, isLoading } = useVoice()

    const handleClick = () => {
        if (isPlaying) {
            stop()
        } else {
            // Strip markdown formatting for cleaner speech
            const cleanText = text
                .replace(/```[\s\S]*?```/g, ' code block omitted ')
                .replace(/`[^`]+`/g, (m) => m.slice(1, -1))
                .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
                .replace(/[#*_~>]/g, '')
                .replace(/\n{2,}/g, '. ')
                .replace(/\n/g, ' ')
                .trim()
            speak(cleanText)
        }
    }

    return (
        <button
            onClick={(e) => {
                e.preventDefault()
                handleClick()
            }}
            className={`inline-flex items-center gap-1 rounded-md border border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-900/40 px-2 py-1 text-[10px] font-medium transition-all active:scale-[0.98] ${isPlaying
                    ? 'text-cyan-600 dark:text-cyan-400 border-cyan-300 dark:border-cyan-600'
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:border-gray-300 dark:hover:border-gray-500'
                } ${className}`}
            aria-label={isPlaying ? 'Stop reading' : 'Read aloud'}
            title={isPlaying ? 'Stop reading' : 'Read aloud with cloned voice'}
            type="button"
            disabled={isLoading}
        >
            {isLoading ? (
                <svg
                    className="h-3 w-3 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                >
                    <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                    />
                    <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                </svg>
            ) : isPlaying ? (
                <svg
                    className="h-3 w-3"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    aria-hidden="true"
                >
                    <path
                        fillRule="evenodd"
                        d="M6 4h3v12H6V4zm5 0h3v12h-3V4z"
                        clipRule="evenodd"
                    />
                </svg>
            ) : (
                <svg
                    className="h-3 w-3"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    aria-hidden="true"
                >
                    <path d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" />
                </svg>
            )}
            <span>
                {isLoading ? 'Generating...' : isPlaying ? 'Stop' : 'Read Aloud'}
            </span>
        </button>
    )
}
