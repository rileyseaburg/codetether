import { useId } from 'react'

import { Button } from '@/components/Button'
import { Container } from '@/components/Container'

function BackgroundIllustration(props: React.ComponentPropsWithoutRef<'div'>) {
  let id = useId()

  return (
    <div {...props}>
      <svg
        viewBox="0 0 1026 1026"
        fill="none"
        aria-hidden="true"
        className="absolute inset-0 h-full w-full animate-spin-slow"
      >
        <path
          d="M1025 513c0 282.77-229.23 512-512 512S1 795.77 1 513 230.23 1 513 1s512 229.23 512 512Z"
          stroke="#D4D4D4"
          strokeOpacity="0.7"
        />
        <path
          d="M513 1025C230.23 1025 1 795.77 1 513"
          stroke={`url(#${id}-gradient-1)`}
          strokeLinecap="round"
        />
        <defs>
          <linearGradient
            id={`${id}-gradient-1`}
            x1="1"
            y1="513"
            x2="1"
            y2="1025"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#06B6D4" />
            <stop offset="1" stopColor="#06B6D4" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
      <svg
        viewBox="0 0 1026 1026"
        fill="none"
        aria-hidden="true"
        className="absolute inset-0 h-full w-full animate-spin-reverse-slower"
      >
        <path
          d="M913 513c0 220.914-179.086 400-400 400S113 733.914 113 513s179.086-400 400-400 400 179.086 400 400Z"
          stroke="#D4D4D4"
          strokeOpacity="0.7"
        />
        <path
          d="M913 513c0 220.914-179.086 400-400 400"
          stroke={`url(#${id}-gradient-2)`}
          strokeLinecap="round"
        />
        <defs>
          <linearGradient
            id={`${id}-gradient-2`}
            x1="913"
            y1="513"
            x2="913"
            y2="913"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#06B6D4" />
            <stop offset="1" stopColor="#06B6D4" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  )
}

function PlayIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
    </svg>
  )
}

export function Hero() {
  return (
    <div className="overflow-hidden pt-14 pb-16 sm:pt-24 sm:pb-24 lg:pt-32 lg:pb-32 xl:pb-36 bg-gray-950">
      <Container>
        <div className="lg:grid lg:grid-cols-12 lg:gap-x-8 lg:gap-y-20">
          <div className="relative z-10 mx-auto max-w-2xl lg:col-span-7 lg:max-w-none lg:pt-6 xl:col-span-6">
            <div className="inline-flex items-center gap-2 rounded-full bg-cyan-950/50 border border-cyan-900/50 px-3 py-1 mb-4">
              <span className="text-xs font-medium text-cyan-400">Powered by RLM</span>
              <span className="text-xs text-gray-400">Unlimited context. Zero degradation.</span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight leading-tight text-white sm:text-4xl lg:text-5xl">
              AI That Works.<br />
              <span className="text-cyan-400">You Get Results.</span>
            </h1>
            <p className="mt-6 text-lg text-gray-300">
              Stop babysitting ChatGPT. Stop paying VAs $1,800/mo for repeatable tasks.
              CodeTether is an <span className="font-semibold text-white">AI worker</span> that 
              runs in the background and delivers real files when done.
            </p>
            <p className="mt-4 text-base text-gray-400">
              Use the web dashboard, iOS app, webhook API, or automate with Zapier.
              Get CSV, PDF, or code delivered however you want.
            </p>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-4">
              <Button href="/dashboard/sessions" color="cyan">
                <PlayIcon className="h-5 w-5 flex-none" />
                <span className="ml-2.5">Open Dashboard</span>
              </Button>
              <Button
                href="/register"
                variant="outline"
                className="text-gray-300"
              >
                <span>Start Free</span>
              </Button>
            </div>
          </div>
          <div className="relative mt-10 sm:mt-20 lg:col-span-5 lg:row-span-2 lg:mt-0 xl:col-span-6">
            <BackgroundIllustration className="absolute top-4 left-1/2 h-[1026px] w-[1026px] -translate-x-1/3 mask-[linear-gradient(to_bottom,white_20%,transparent_75%)] stroke-gray-700/50 sm:top-16 sm:-translate-x-1/2 lg:-top-16 lg:ml-12 xl:-top-14 xl:ml-0" />
            <div className="-mx-4 h-[448px] px-9 sm:mx-0 lg:absolute lg:-inset-x-10 lg:-top-10 lg:-bottom-20 lg:h-auto lg:px-0 lg:pt-10 xl:-bottom-32">
              <div className="mx-auto max-w-[500px] rounded-2xl bg-gray-900 p-4 shadow-2xl ring-1 ring-gray-800">
                {/* Ways to Use */}
                <div className="grid grid-cols-2 gap-3">
                  {/* Web Dashboard */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center mb-3">
                      <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <span className="font-medium text-white text-sm">Web Dashboard</span>
                    <p className="text-xs text-gray-400 mt-1">Chat sessions with file output</p>
                  </div>

                  {/* iOS App */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center mb-3">
                      <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <span className="font-medium text-white text-sm">iOS App</span>
                    <p className="text-xs text-gray-400 mt-1">Tasks from your phone</p>
                  </div>

                  {/* Webhook API */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center mb-3">
                      <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <span className="font-medium text-white text-sm">Webhook API</span>
                    <p className="text-xs text-gray-400 mt-1">Trigger programmatically</p>
                  </div>

                  {/* Zapier/n8n */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center mb-3">
                      <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    </div>
                    <span className="font-medium text-white text-sm">Zapier / n8n</span>
                    <p className="text-xs text-gray-400 mt-1">No-code automation</p>
                  </div>
                </div>

                {/* Output */}
                <div className="mt-4 rounded-xl bg-cyan-950/50 border border-cyan-900 p-4">
                  <p className="text-xs text-gray-400 mb-2">All methods deliver real output:</p>
                  <div className="flex flex-wrap gap-2">
                    <span className="inline-flex items-center rounded bg-gray-800 px-2 py-1 text-xs text-cyan-400">CSV</span>
                    <span className="inline-flex items-center rounded bg-gray-800 px-2 py-1 text-xs text-cyan-400">PDF</span>
                    <span className="inline-flex items-center rounded bg-gray-800 px-2 py-1 text-xs text-cyan-400">Code</span>
                    <span className="inline-flex items-center rounded bg-gray-800 px-2 py-1 text-xs text-cyan-400">Reports</span>
                  </div>
                </div>

                {/* RLM Badge */}
                <div className="mt-3 flex items-center justify-center gap-2 text-xs text-gray-500">
                  <svg className="h-3 w-3 text-cyan-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span>Handles 10M+ tokens via RLM</span>
                </div>
              </div>
            </div>
          </div>
          <div className="relative -mt-4 lg:col-span-7 lg:mt-0 xl:col-span-6">
            <p className="text-center text-sm font-semibold text-gray-400 lg:text-left">
              Use it your way
            </p>
            <ul
              role="list"
              className="mx-auto mt-8 flex max-w-xl flex-wrap justify-center gap-x-8 gap-y-4 lg:mx-0 lg:justify-start"
            >
              {[
                ['Web', 'Dashboard'],
                ['iOS', 'App Store'],
                ['API', 'Webhook'],
                ['Zapier', 'No-code'],
                ['Email', 'Reply to refine'],
              ].map(([name, desc]) => (
                <li key={name} className="text-center">
                  <span className="block text-sm font-medium text-gray-300">{name}</span>
                  <span className="block text-xs text-gray-500">{desc}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Container>
    </div>
  )
}
