'use client'

import { CameraCapture } from './components/CameraCapture'

export default function AvatarPage() {
    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                    AI Avatar Studio
                </h1>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Create lip-synced AI avatar videos. Use <strong>Selfie mode</strong> to capture
                    multiple angles of your face for 3D avatar generation, or use <strong>Photo/Video</strong> mode
                    for direct Duix lip-sync. Write your script and generate a professional avatar video.
                </p>
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
                <CameraCapture />
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    How it works
                </h2>
                <div className="grid gap-4 sm:grid-cols-4">
                    <Step
                        number={1}
                        title="Capture"
                        description="Take a photo or record a short video of yourself facing the camera."
                    />
                    <Step
                        number={2}
                        title="Write Script"
                        description="Enter the text you want your avatar to speak."
                    />
                    <Step
                        number={3}
                        title="Generate"
                        description="The AI clones your face and lip-syncs it to the script using Duix Avatar."
                    />
                    <Step
                        number={4}
                        title="Publish"
                        description="Download or publish your avatar video directly to YouTube."
                    />
                </div>
            </div>
        </div>
    )
}

function Step({
    number,
    title,
    description,
}: {
    number: number
    title: string
    description: string
}) {
    return (
        <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cyan-100 text-sm font-bold text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300">
                {number}
            </div>
            <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                    {title}
                </h3>
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                    {description}
                </p>
            </div>
        </div>
    )
}
