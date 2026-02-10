'use client'

import { useState, useRef, useCallback, useEffect } from 'react'

interface UseCameraOptions {
    /** Preferred facing mode */
    facingMode?: 'user' | 'environment'
    /** Video width constraint */
    width?: number
    /** Video height constraint */
    height?: number
}

interface UseCameraReturn {
    /** Ref to attach to a <video> element for live preview */
    videoRef: React.RefObject<HTMLVideoElement | null>
    /** Whether the camera stream is active */
    isActive: boolean
    /** Start the camera stream */
    start: () => Promise<void>
    /** Stop the camera stream */
    stop: () => void
    /** Capture a still photo as a Blob (PNG) */
    capturePhoto: () => Blob | null
    /** Start recording a short video clip */
    startRecording: () => void
    /** Stop recording and return the video Blob */
    stopRecording: () => Promise<Blob | null>
    /** Whether currently recording video */
    isRecording: boolean
    /** Recording duration in seconds */
    recordingDuration: number
    /** Error message */
    error: string | null
    /** Available video input devices */
    devices: MediaDeviceInfo[]
    /** Currently selected device ID (empty = default) */
    selectedDeviceId: string
    /** Select a specific camera device by ID */
    selectDevice: (deviceId: string) => void
}

export function useCamera(options: UseCameraOptions = {}): UseCameraReturn {
    const { facingMode = 'user', width = 1280, height = 720 } = options

    const videoRef = useRef<HTMLVideoElement | null>(null)
    const streamRef = useRef<MediaStream | null>(null)
    const recorderRef = useRef<MediaRecorder | null>(null)
    const chunksRef = useRef<Blob[]>([])
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

    const [isActive, setIsActive] = useState(false)
    const [isRecording, setIsRecording] = useState(false)
    const [recordingDuration, setRecordingDuration] = useState(0)
    const [error, setError] = useState<string | null>(null)
    const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
    const [selectedDeviceId, setSelectedDeviceId] = useState('')

    const stop = useCallback(() => {
        if (recorderRef.current?.state === 'recording') {
            recorderRef.current.stop()
        }
        recorderRef.current = null
        if (timerRef.current) {
            clearInterval(timerRef.current)
            timerRef.current = null
        }
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop())
            streamRef.current = null
        }
        if (videoRef.current) {
            videoRef.current.srcObject = null
        }
        setIsActive(false)
        setIsRecording(false)
        setRecordingDuration(0)
    }, [])

    const enumerateDevices = useCallback(async () => {
        try {
            const allDevices = await navigator.mediaDevices.enumerateDevices()
            const videoDevices = allDevices.filter((d) => d.kind === 'videoinput')
            setDevices(videoDevices)
        } catch {
            // Ignore enumeration errors
        }
    }, [])

    const start = useCallback(async () => {
        stop()
        setError(null)
        try {
            const videoConstraints: MediaTrackConstraints = {
                width: { ideal: width },
                height: { ideal: height },
            }
            if (selectedDeviceId) {
                videoConstraints.deviceId = { exact: selectedDeviceId }
            } else {
                videoConstraints.facingMode = facingMode
            }
            const stream = await navigator.mediaDevices.getUserMedia({
                video: videoConstraints,
                audio: true,
            })
            streamRef.current = stream
            if (videoRef.current) {
                videoRef.current.srcObject = stream
                videoRef.current.muted = true
                await videoRef.current.play()
            }
            setIsActive(true)
            // Enumerate after getting permission (labels become available)
            await enumerateDevices()
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Camera access denied'
            setError(msg)
        }
    }, [facingMode, width, height, stop, selectedDeviceId, enumerateDevices])

    const selectDevice = useCallback((deviceId: string) => {
        setSelectedDeviceId(deviceId)
    }, [])

    const capturePhoto = useCallback((): Blob | null => {
        const video = videoRef.current
        if (!video || !isActive) return null

        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        const ctx = canvas.getContext('2d')
        if (!ctx) return null

        ctx.drawImage(video, 0, 0)

        let blob: Blob | null = null
        canvas.toBlob((b) => { blob = b }, 'image/png')
        // toBlob is async, use synchronous approach
        const dataUrl = canvas.toDataURL('image/png')
        const binary = atob(dataUrl.split(',')[1])
        const array = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i++) array[i] = binary.charCodeAt(i)
        return new Blob([array], { type: 'image/png' })
    }, [isActive])

    const startRecording = useCallback(() => {
        if (!streamRef.current || isRecording) return

        chunksRef.current = []
        const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
            ? 'video/webm;codecs=vp9'
            : 'video/webm'
        const recorder = new MediaRecorder(streamRef.current, { mimeType })
        recorderRef.current = recorder

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) chunksRef.current.push(e.data)
        }

        recorder.start(100) // collect data every 100ms
        setIsRecording(true)
        setRecordingDuration(0)

        const startTime = Date.now()
        timerRef.current = setInterval(() => {
            setRecordingDuration(Math.floor((Date.now() - startTime) / 1000))
        }, 500)
    }, [isRecording])

    const stopRecording = useCallback((): Promise<Blob | null> => {
        return new Promise((resolve) => {
            const recorder = recorderRef.current
            if (!recorder || recorder.state !== 'recording') {
                resolve(null)
                return
            }

            if (timerRef.current) {
                clearInterval(timerRef.current)
                timerRef.current = null
            }

            recorder.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
                chunksRef.current = []
                setIsRecording(false)
                resolve(blob)
            }

            recorder.stop()
        })
    }, [])

    // Enumerate devices on mount (labels may be empty until permission granted)
    useEffect(() => {
        enumerateDevices()
    }, [enumerateDevices])

    // Auto-restart camera when device selection changes
    useEffect(() => {
        if (isActive && selectedDeviceId) {
            start()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedDeviceId])

    // Cleanup on unmount
    useEffect(() => {
        return () => { stop() }
    }, [stop])

    return {
        videoRef,
        isActive,
        start,
        stop,
        capturePhoto,
        startRecording,
        stopRecording,
        isRecording,
        recordingDuration,
        error,
        devices,
        selectedDeviceId,
        selectDevice,
    }
}
