'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { useCamera } from '@/hooks/useCamera'

const VOICE_API_URL =
    process.env.NEXT_PUBLIC_VOICE_API_URL || 'https://voice.quantum-forge.io'

type CaptureMode = 'photo' | 'video' | 'selfies'
type UploadStatus = 'idle' | 'uploading' | 'success' | 'error'

interface AvatarResult {
    videoUrl?: string
    status?: string
    taskCode?: string
    message?: string
}

interface SelfieSlot {
    label: string
    instruction: string
    blob: Blob | null
    preview: string | null
}

const SELFIE_POSES: { label: string; instruction: string }[] = [
    { label: 'Front', instruction: 'Look straight at the camera, neutral expression' },
    { label: 'Smile', instruction: 'Look straight at the camera and smile' },
    { label: 'Left 45\u00b0', instruction: 'Turn your head 45\u00b0 to the left' },
    { label: 'Right 45\u00b0', instruction: 'Turn your head 45\u00b0 to the right' },
    { label: 'Left Profile', instruction: 'Turn your head fully to the left (profile view)' },
    { label: 'Right Profile', instruction: 'Turn your head fully to the right' },
    { label: 'Look Up', instruction: 'Tilt your chin up slightly' },
    { label: 'Look Down', instruction: 'Tilt your chin down slightly' },
    { label: 'Close-up', instruction: 'Move closer to the camera (face fills frame)' },
    { label: 'Expression', instruction: 'Show a surprised or animated expression' },
    { label: 'Talking', instruction: 'Open your mouth as if speaking mid-word' },
    { label: 'Extra', instruction: 'Any additional angle you like' },
]

export function CameraCapture() {
    const {
        videoRef,
        isActive,
        start,
        stop,
        capturePhoto,
        startRecording,
        stopRecording,
        isRecording,
        recordingDuration,
        error: cameraError,
        devices,
        selectedDeviceId,
        selectDevice,
    } = useCamera({ facingMode: 'user', width: 1080, height: 1080 })

    const [mode, setMode] = useState<CaptureMode>('selfies')
    const [capturedPhoto, setCapturedPhoto] = useState<string | null>(null)
    const [capturedVideo, setCapturedVideo] = useState<string | null>(null)
    const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null)
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle')
    const [uploadMessage, setUploadMessage] = useState('')
    const [avatarResult, setAvatarResult] = useState<AvatarResult | null>(null)
    const [avatarScript, setAvatarScript] = useState(
        "What if your code could write itself? Meet CodeTether, the autonomous AI agent that doesn't just assist \u2014 it builds. From writing production-ready code to running tests and deploying, CodeTether handles the entire development lifecycle. With over 30 integrated tools, voice cloning, and real-time collaboration, it's like having a senior developer who never sleeps."
    )

    // Multi-selfie state
    const [selfies, setSelfies] = useState<SelfieSlot[]>(
        SELFIE_POSES.map((p) => ({ ...p, blob: null, preview: null }))
    )
    const [activeSelfieIdx, setActiveSelfieIdx] = useState(0)

    const selfieCount = selfies.filter((s) => s.blob !== null).length

    const handleCapture = useCallback(() => {
        if (mode === 'photo') {
            const blob = capturePhoto()
            if (blob) {
                setCapturedPhoto(URL.createObjectURL(blob))
                setCapturedBlob(blob)
                setCapturedVideo(null)
            }
        }
    }, [mode, capturePhoto])

    const handleSelfieCaptureAtIndex = useCallback(
        (idx: number) => {
            const blob = capturePhoto()
            if (!blob) return
            const preview = URL.createObjectURL(blob)
            setSelfies((prev) => {
                const next = [...prev]
                // Revoke old preview URL
                if (next[idx].preview) URL.revokeObjectURL(next[idx].preview!)
                next[idx] = { ...next[idx], blob, preview }
                return next
            })
            // Auto-advance to next empty slot
            const nextEmpty = selfies.findIndex((s, i) => i > idx && s.blob === null)
            if (nextEmpty !== -1) setActiveSelfieIdx(nextEmpty)
        },
        [capturePhoto, selfies]
    )

    const handleSelfieRemove = useCallback((idx: number) => {
        setSelfies((prev) => {
            const next = [...prev]
            if (next[idx].preview) URL.revokeObjectURL(next[idx].preview!)
            next[idx] = { ...next[idx], blob: null, preview: null }
            return next
        })
    }, [])

    const handleStartRecording = useCallback(() => {
        setCapturedPhoto(null)
        setCapturedVideo(null)
        setCapturedBlob(null)
        startRecording()
    }, [startRecording])

    const handleStopRecording = useCallback(async () => {
        const blob = await stopRecording()
        if (blob) {
            setCapturedVideo(URL.createObjectURL(blob))
            setCapturedBlob(blob)
            setCapturedPhoto(null)
        }
    }, [stopRecording])

    const handleRetake = useCallback(() => {
        setCapturedPhoto(null)
        setCapturedVideo(null)
        setCapturedBlob(null)
        setUploadStatus('idle')
        setUploadMessage('')
        setAvatarResult(null)
    }, [])

    const handleUpload = useCallback(async () => {
        // For selfie mode, upload all captured selfies
        if (mode === 'selfies') {
            const captured = selfies.filter((s) => s.blob !== null)
            if (captured.length < 3) {
                setUploadStatus('error')
                setUploadMessage('Capture at least 3 selfies from different angles.')
                return
            }

            setUploadStatus('uploading')
            setUploadMessage(`Uploading ${captured.length} selfies to avatar service...`)

            try {
                const formData = new FormData()
                formData.append('name', `selfie_set_${Date.now()}`)
                captured.forEach((s, i) => {
                    formData.append('selfies', s.blob!, `selfie_${i}_${s.label.replace(/\s+/g, '_')}.png`)
                })
                formData.append('script', avatarScript)

                const uploadRes = await fetch(`${VOICE_API_URL}/avatar/upload-selfies`, {
                    method: 'POST',
                    body: formData,
                })

                if (!uploadRes.ok) {
                    const errBody = await uploadRes.text()
                    throw new Error(`Upload failed (${uploadRes.status}): ${errBody}`)
                }

                const data = await uploadRes.json()
                const videoUrl = data.video_path
                    ? `${VOICE_API_URL}/avatar/video/${data.video_path.split('/').pop()}`
                    : undefined
                setAvatarResult({ ...data, videoUrl })
                setUploadStatus('success')
                setUploadMessage(`${captured.length} selfies uploaded! ${data.message || 'Avatar generation started.'}`)
            } catch (err) {
                setUploadStatus('error')
                setUploadMessage(err instanceof Error ? err.message : 'Upload failed')
            }
            return
        }

        // Photo/video single upload
        if (!capturedBlob) return

        setUploadStatus('uploading')
        setUploadMessage('Uploading model to avatar service...')

        try {
            const formData = new FormData()
            const ext = mode === 'photo' ? 'png' : 'webm'
            const filename = `camera_model.${ext}`
            formData.append('video', capturedBlob, filename)
            formData.append('name', `camera_${Date.now()}`)

            const uploadRes = await fetch(`${VOICE_API_URL}/avatar/upload-model`, {
                method: 'POST',
                body: formData,
            })

            if (!uploadRes.ok) {
                const errBody = await uploadRes.text()
                throw new Error(`Upload failed (${uploadRes.status}): ${errBody}`)
            }

            const uploadData = await uploadRes.json()
            setUploadMessage('Model uploaded. Generating avatar video...')

            // Generate avatar with this model and the script
            const genFormData = new FormData()
            genFormData.append('text', avatarScript)
            if (uploadData.model_path) {
                genFormData.append('model_video', uploadData.model_path)
            }

            const genRes = await fetch(`${VOICE_API_URL}/avatar/generate`, {
                method: 'POST',
                body: genFormData,
            })

            if (!genRes.ok) {
                const errBody = await genRes.text()
                throw new Error(`Generation failed (${genRes.status}): ${errBody}`)
            }

            const genData = await genRes.json()
            if (genData.error) {
                throw new Error(genData.error)
            }

            // Convert server path to serving URL
            const videoUrl = genData.video_path
                ? `${VOICE_API_URL}/avatar/video/${genData.video_path.split('/').pop()}`
                : undefined
            setAvatarResult({ ...genData, videoUrl })
            setUploadStatus('success')
            setUploadMessage('Avatar video generated!')
        } catch (err) {
            setUploadStatus('error')
            setUploadMessage(err instanceof Error ? err.message : 'Upload failed')
        }
    }, [capturedBlob, mode, avatarScript, selfies])

    const hasCaptured = !!capturedPhoto || !!capturedVideo

    return (
        <div className="space-y-6">
            {/* Camera Controls Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setMode('selfies')}
                        className={`rounded-lg px-4 py-2 text-sm font-medium transition ${mode === 'selfies'
                            ? 'bg-purple-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300'
                            }`}
                    >
                        <span className="flex items-center gap-2">
                            <GridIcon className="h-4 w-4" />
                            Selfies ({selfieCount}/12)
                        </span>
                    </button>
                    <button
                        onClick={() => setMode('photo')}
                        className={`rounded-lg px-4 py-2 text-sm font-medium transition ${mode === 'photo'
                            ? 'bg-cyan-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300'
                            }`}
                    >
                        <span className="flex items-center gap-2">
                            <CameraIcon className="h-4 w-4" />
                            Photo
                        </span>
                    </button>
                    <button
                        onClick={() => setMode('video')}
                        className={`rounded-lg px-4 py-2 text-sm font-medium transition ${mode === 'video'
                            ? 'bg-cyan-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300'
                            }`}
                    >
                        <span className="flex items-center gap-2">
                            <VideoCameraIcon className="h-4 w-4" />
                            Video
                        </span>
                    </button>
                </div>
                <div className="flex items-center gap-2">
                    <select
                        value={selectedDeviceId}
                        onChange={(e) => selectDevice(e.target.value)}
                        className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300"
                    >
                        <option value="">Default Camera</option>
                        {devices.map((d, i) => (
                            <option key={d.deviceId} value={d.deviceId}>
                                {d.label || `Camera ${i + 1}`}
                            </option>
                        ))}
                    </select>
                    {!isActive ? (
                        <button
                            onClick={start}
                            className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500"
                        >
                            <PowerIcon className="h-4 w-4" />
                            Start Camera
                        </button>
                    ) : (
                        <button
                            onClick={stop}
                            className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
                        >
                            <PowerIcon className="h-4 w-4" />
                            Stop Camera
                        </button>
                    )}
                </div>
            </div>

            {cameraError && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
                    {cameraError}
                </div>
            )}

            {/* MAIN LAYOUT: Live Preview + Mode-specific panel */}
            <div className={`grid gap-6 ${mode === 'selfies' ? 'lg:grid-cols-2' : 'lg:grid-cols-2'}`}>
                {/* Live Preview (shared across all modes — single <video> element) */}
                <div className="space-y-3">
                    <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Live Preview
                    </h3>
                    <div className={`relative aspect-square overflow-hidden rounded-xl border-2 bg-black ${mode === 'selfies'
                        ? 'border-purple-300 dark:border-purple-700'
                        : 'border-gray-200 dark:border-gray-700'
                        }`}>
                        <video
                            ref={videoRef}
                            className="h-full w-full object-cover"
                            autoPlay
                            playsInline
                            muted
                            style={{ transform: 'scaleX(-1)' }}
                        />
                        {!isActive && (
                            <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80">
                                <div className="text-center text-gray-400">
                                    <CameraIcon className="mx-auto h-12 w-12 mb-2" />
                                    <p className="text-sm">Click &quot;Start Camera&quot; to begin</p>
                                </div>
                            </div>
                        )}
                        {/* Selfie pose overlay */}
                        {mode === 'selfies' && isActive && (
                            <div className="absolute bottom-0 left-0 right-0 bg-linear-to-t from-black/80 to-transparent p-4">
                                <p className="text-xs text-purple-300 font-medium">
                                    Pose {activeSelfieIdx + 1}/12: {selfies[activeSelfieIdx].label}
                                </p>
                                <p className="text-sm text-white font-medium mt-1">
                                    {selfies[activeSelfieIdx].instruction}
                                </p>
                            </div>
                        )}
                        {/* Recording overlay */}
                        {isRecording && (
                            <div className="absolute top-3 left-3 flex items-center gap-2 rounded-full bg-red-600 px-3 py-1 text-xs font-medium text-white">
                                <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                                REC {recordingDuration}s
                            </div>
                        )}
                        {isRecording && (
                            <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-700">
                                <div
                                    className="h-full bg-red-500 transition-all duration-500"
                                    style={{ width: `${Math.min((recordingDuration / 45) * 100, 100)}%` }}
                                />
                            </div>
                        )}
                    </div>

                    {/* Capture Buttons */}
                    <div className="flex justify-center gap-3">
                        {mode === 'selfies' && isActive && (
                            <button
                                onClick={() => handleSelfieCaptureAtIndex(activeSelfieIdx)}
                                className="inline-flex items-center gap-2 rounded-full bg-purple-600 px-6 py-3 text-sm font-medium text-white shadow-lg ring-2 ring-purple-400 hover:bg-purple-500"
                            >
                                <div className="h-6 w-6 rounded-full border-4 border-white/80" />
                                Capture &quot;{selfies[activeSelfieIdx].label}&quot;
                            </button>
                        )}
                        {mode === 'photo' && isActive && (
                            <button
                                onClick={handleCapture}
                                className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-medium text-gray-900 shadow-lg ring-2 ring-cyan-500 hover:bg-gray-50"
                            >
                                <div className="h-6 w-6 rounded-full border-4 border-cyan-500" />
                                Capture Photo
                            </button>
                        )}
                        {mode === 'video' && isActive && !isRecording && (
                            <button
                                onClick={handleStartRecording}
                                className="inline-flex items-center gap-2 rounded-full bg-red-600 px-6 py-3 text-sm font-medium text-white shadow-lg hover:bg-red-500"
                            >
                                <div className="h-4 w-4 rounded-full bg-white" />
                                Start Recording
                            </button>
                        )}
                        {mode === 'video' && isRecording && (
                            <button
                                onClick={handleStopRecording}
                                className="inline-flex items-center gap-2 rounded-full bg-gray-800 px-6 py-3 text-sm font-medium text-white shadow-lg ring-2 ring-red-500 hover:bg-gray-700"
                            >
                                <div className="h-4 w-4 rounded bg-red-500" />
                                Stop ({recordingDuration}s)
                            </button>
                        )}
                    </div>
                    <p className="text-center text-xs text-gray-500 dark:text-gray-400">
                        {mode === 'selfies'
                            ? 'Follow the pose guide above, then capture each angle'
                            : mode === 'photo'
                                ? 'Take a clear, front-facing photo with good lighting'
                                : 'Record 5-15 seconds of you speaking naturally (face centered)'}
                    </p>
                </div>

                {/* RIGHT PANEL: Selfie Gallery or Captured Content */}
                {mode === 'selfies' ? (
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                Selfie Gallery ({selfieCount}/12)
                            </h3>
                            {selfieCount > 0 && (
                                <button
                                    onClick={() => {
                                        selfies.forEach((s) => { if (s.preview) URL.revokeObjectURL(s.preview) })
                                        setSelfies(SELFIE_POSES.map((p) => ({ ...p, blob: null, preview: null })))
                                        setActiveSelfieIdx(0)
                                    }}
                                    className="text-xs text-red-500 hover:text-red-400"
                                >
                                    Clear all
                                </button>
                            )}
                        </div>
                        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                            {selfies.map((slot, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => setActiveSelfieIdx(idx)}
                                    className={`group relative aspect-square overflow-hidden rounded-lg border-2 transition ${activeSelfieIdx === idx
                                        ? 'border-purple-500 ring-2 ring-purple-500/30'
                                        : slot.blob
                                            ? 'border-green-400 dark:border-green-600'
                                            : 'border-gray-200 dark:border-gray-700'
                                        }`}
                                >
                                    {slot.preview ? (
                                        <>
                                            <img
                                                src={slot.preview}
                                                alt={slot.label}
                                                className="h-full w-full object-cover"
                                                style={{ transform: 'scaleX(-1)' }}
                                            />
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleSelfieRemove(idx) }}
                                                className="absolute top-1 right-1 hidden h-5 w-5 items-center justify-center rounded-full bg-red-600 text-[10px] text-white group-hover:flex"
                                            >
                                                {'\u00d7'}
                                            </button>
                                        </>
                                    ) : (
                                        <div className="flex h-full w-full flex-col items-center justify-center bg-gray-50 text-gray-400 dark:bg-gray-800">
                                            <span className="text-[10px] font-medium">{slot.label}</span>
                                        </div>
                                    )}
                                    <div className={`absolute bottom-0.5 left-0.5 flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold ${slot.blob ? 'bg-green-500 text-white' : 'bg-gray-300 text-gray-600 dark:bg-gray-600 dark:text-gray-300'
                                        }`}>
                                        {idx + 1}
                                    </div>
                                </button>
                            ))}
                        </div>

                        <div className="flex justify-center gap-3 pt-2">
                            <button
                                onClick={handleUpload}
                                disabled={selfieCount < 3 || uploadStatus === 'uploading'}
                                className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50"
                            >
                                {uploadStatus === 'uploading' ? (
                                    <>
                                        <SpinnerIcon className="h-4 w-4 animate-spin" />
                                        Uploading {selfieCount} selfies...
                                    </>
                                ) : (
                                    <>
                                        <SparklesIcon className="h-4 w-4" />
                                        Generate 3D Avatar ({selfieCount} selfies)
                                    </>
                                )}
                            </button>
                        </div>

                        {selfieCount < 3 && (
                            <div className="space-y-1">
                                <div className="h-1.5 rounded-full bg-gray-200 dark:bg-gray-700">
                                    <div
                                        className="h-full rounded-full bg-purple-500 transition-all"
                                        style={{ width: `${(selfieCount / 3) * 100}%` }}
                                    />
                                </div>
                                <p className="text-center text-xs text-gray-500">
                                    Capture at least 3 selfies (10+ recommended for best quality)
                                </p>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="space-y-3">
                        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                            {hasCaptured ? 'Captured' : 'Result'}
                        </h3>
                        <div className="relative aspect-square overflow-hidden rounded-xl border-2 border-gray-200 bg-gray-900 dark:border-gray-700">
                            {capturedPhoto && (
                                <img
                                    src={capturedPhoto}
                                    alt="Captured photo"
                                    className="h-full w-full object-cover"
                                    style={{ transform: 'scaleX(-1)' }}
                                />
                            )}
                            {capturedVideo && (
                                <video
                                    src={capturedVideo}
                                    className="h-full w-full object-cover"
                                    controls
                                    autoPlay
                                    loop
                                    style={{ transform: 'scaleX(-1)' }}
                                />
                            )}
                            {avatarResult?.videoUrl && (
                                <video
                                    src={avatarResult.videoUrl}
                                    className="h-full w-full object-cover"
                                    controls
                                    autoPlay
                                />
                            )}
                            {!hasCaptured && !avatarResult?.videoUrl && (
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="text-center text-gray-500">
                                        <SparklesIcon className="mx-auto h-12 w-12 mb-2" />
                                        <p className="text-sm">Capture will appear here</p>
                                    </div>
                                </div>
                            )}
                        </div>

                        {hasCaptured && (
                            <div className="flex justify-center gap-3">
                                <button
                                    onClick={handleRetake}
                                    className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                                >
                                    Retake
                                </button>
                                <button
                                    onClick={handleUpload}
                                    disabled={uploadStatus === 'uploading'}
                                    className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
                                >
                                    {uploadStatus === 'uploading' ? (
                                        <>
                                            <SpinnerIcon className="h-4 w-4 animate-spin" />
                                            Processing...
                                        </>
                                    ) : (
                                        <>
                                            <SparklesIcon className="h-4 w-4" />
                                            Generate Avatar
                                        </>
                                    )}
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Status Messages */}
            {uploadMessage && (
                <div
                    className={`rounded-lg border p-3 text-sm ${uploadStatus === 'error'
                        ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400'
                        : uploadStatus === 'success'
                            ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-900/30 dark:text-green-400'
                            : mode === 'selfies'
                                ? 'border-purple-200 bg-purple-50 text-purple-700 dark:border-purple-800 dark:bg-purple-900/30 dark:text-purple-400'
                                : 'border-cyan-200 bg-cyan-50 text-cyan-700 dark:border-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400'
                        }`}
                >
                    {uploadMessage}
                </div>
            )}

            {/* Avatar Result Video */}
            {avatarResult?.videoUrl && mode === 'selfies' && (
                <div className="space-y-2">
                    <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Generated Avatar
                    </h3>
                    <div className="aspect-video overflow-hidden rounded-xl border-2 border-green-400 bg-black">
                        <video
                            src={avatarResult.videoUrl}
                            className="h-full w-full object-contain"
                            controls
                            autoPlay
                        />
                    </div>
                </div>
            )}

            {/* Script Editor */}
            <div className="space-y-2">
                <label
                    htmlFor="avatar-script"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                    Avatar Script
                </label>
                <textarea
                    id="avatar-script"
                    value={avatarScript}
                    onChange={(e) => setAvatarScript(e.target.value)}
                    rows={4}
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                    placeholder="Enter the text your avatar will speak..."
                />
                <p className="text-xs text-gray-500">
                    This text will be spoken by your AI avatar using Riley&apos;s cloned voice.
                </p>
            </div>
        </div>
    )
}

// Inline SVG icons
function GridIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
    )
}

function CameraIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
        </svg>
    )
}

function VideoCameraIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
            <path strokeLinecap="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9.75a2.25 2.25 0 002.25-2.25V7.5a2.25 2.25 0 00-2.25-2.25H4.5A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
        </svg>
    )
}

function PowerIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
        </svg>
    )
}

function SparklesIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
        </svg>
    )
}

function SpinnerIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" {...props}>
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
    )
}
