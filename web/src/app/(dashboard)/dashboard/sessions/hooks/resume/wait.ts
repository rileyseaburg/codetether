export function wait(ms: number, signal: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
        const abort = () => {
            clearTimeout(timer)
            reject(new Error('Polling stopped.'))
        }
        const timer = setTimeout(() => {
            signal.removeEventListener('abort', abort)
            resolve()
        }, ms)
        signal.addEventListener('abort', abort, { once: true })
        if (signal.aborted) abort()
    })
}
