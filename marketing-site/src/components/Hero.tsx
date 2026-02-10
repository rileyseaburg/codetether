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
            <div className="inline-flex items-center gap-2 rounded-full bg-cyan-950/40 border border-cyan-900/50 px-3 py-1 mb-4">
              <span className="text-xs font-medium text-cyan-400">v1.1.0 Shipped</span>
              <span className="text-xs text-gray-400">Mandatory auth · Audit trail · Ed25519 plugin signing · K8s self-deploy</span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight leading-tight text-white sm:text-4xl lg:text-5xl">
              The AI agent your infrastructure<br />
              <span className="text-cyan-400">actually deserves.</span>
            </h1>
            <p className="mt-6 text-lg text-gray-300">
              A perpetual cognition runtime written in <span className="font-semibold text-white">Rust</span>, self-deploying on <span className="font-semibold text-white">Kubernetes</span>, with mandatory auth and sandboxed plugins. Not a chatbot — <span className="text-cyan-300">infrastructure.</span>
            </p>
            <p className="mt-4 text-base text-gray-400">
              Open source. Free to self-host. Built by someone who runs production systems for a living.
            </p>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-4">
              <Button href="/register" color="cyan">
                <span>Deploy CodeTether Free</span>
              </Button>
              <Button
                href="#openclaw-comparison"
                variant="outline"
                className="text-gray-300"
              >
                <span>See Why We Built This ↓</span>
              </Button>
            </div>
            <p className="mt-6 text-xs text-gray-500">
              MIT License. No credit card required. Read the code, audit the architecture, deploy on your terms.
            </p>

            {/* What makes it different */}
            <div className="mt-12 pt-8 border-t border-gray-800">
              <p className="text-xs text-gray-400 font-medium mb-4">Shipped in v1.1.0 — not a roadmap, it&apos;s in the binary:</p>
              <div className="grid sm:grid-cols-3 gap-4">
                <div className="rounded-lg bg-gray-900/50 p-3 border border-gray-800">
                  <p className="text-sm text-white font-medium">Mandatory Auth</p>
                  <p className="text-xs text-gray-400 mt-1">HMAC-SHA256 tokens. Cannot be disabled. Every endpoint.</p>
                </div>
                <div className="rounded-lg bg-gray-900/50 p-3 border border-gray-800">
                  <p className="text-sm text-white font-medium">Plugin Signing</p>
                  <p className="text-xs text-gray-400 mt-1">Ed25519 signatures + SHA-256 integrity on every tool.</p>
                </div>
                <div className="rounded-lg bg-gray-900/50 p-3 border border-gray-800">
                  <p className="text-sm text-white font-medium">Audit Trail</p>
                  <p className="text-xs text-gray-400 mt-1">Append-only JSON Lines. Every action. Queryable.</p>
                </div>
              </div>
            </div>
          </div>
          <div className="relative mt-10 sm:mt-20 lg:col-span-5 lg:row-span-2 lg:mt-0 xl:col-span-6">
            <BackgroundIllustration className="absolute top-4 left-1/2 h-[1026px] w-[1026px] -translate-x-1/3 mask-[linear-gradient(to_bottom,white_20%,transparent_75%)] stroke-gray-700/50 sm:top-16 sm:-translate-x-1/2 lg:-top-16 lg:ml-12 xl:-top-14 xl:ml-0" />
            <div className="-mx-4 h-[448px] px-9 sm:mx-0 lg:absolute lg:-inset-x-10 lg:-top-10 lg:-bottom-20 lg:h-auto lg:px-0 lg:pt-10 xl:-bottom-32">
              <div className="mx-auto max-w-[500px] rounded-2xl bg-gray-900 p-4 shadow-2xl ring-1 ring-gray-800">
                {/* Architecture overview */}
                <div className="space-y-3">
                  {/* Perpetual Cognition */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                        <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12a7.5 7.5 0 0015 0m-15 0a7.5 7.5 0 1115 0m-15 0H3m16.5 0H21m-1.5 0H12m-8.457 3.077l1.41-.513m14.095-5.13l1.41-.513M5.106 17.785l1.15-.964m11.49-9.642l1.149-.964M7.501 19.795l.75-1.3m7.5-12.99l.75-1.3m-6.063 16.658l.26-1.477m2.605-14.772l.26-1.477m0 17.726l-.26-1.477M10.698 4.614l-.26-1.477M16.5 19.794l-.75-1.299M7.5 4.205L12 12m6.894 5.785l-1.149-.964M6.256 7.178l-1.15-.964m15.352 8.864l-1.41-.513M4.954 9.435l-1.41-.514M12.002 12l-3.75 6.495" />
                        </svg>
                      </div>
                      <span className="font-medium text-white text-sm">Perpetual Cognition</span>
                    </div>
                    <p className="text-xs text-gray-400">Continuous thought loops that persist across restarts. Not request-response.</p>
                  </div>

                  {/* Security Comparison */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                        <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                        </svg>
                      </div>
                      <span className="font-medium text-white text-sm">Security-First Architecture</span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-400">Authentication</span>
                        <div className="flex items-center gap-3">
                          <span className="text-red-400 line-through">auth: none</span>
                          <span className="text-cyan-400 font-medium">Mandatory</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-400">Plugin isolation</span>
                        <div className="flex items-center gap-3">
                          <span className="text-red-400 line-through">Shared process</span>
                          <span className="text-cyan-400 font-medium">Sandboxed</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-400">Audit trail</span>
                        <div className="flex items-center gap-3">
                          <span className="text-red-400 line-through">None</span>
                          <span className="text-cyan-400 font-medium">Every action</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Self-Deploying */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                        <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21.75 17.25v-.228a4.5 4.5 0 00-.12-1.03l-2.268-9.64a3.375 3.375 0 00-3.285-2.602H7.923a3.375 3.375 0 00-3.285 2.602l-2.268 9.64a4.5 4.5 0 00-.12 1.03v.228m19.5 0a3 3 0 01-3 3H5.25a3 3 0 01-3-3m19.5 0a3 3 0 00-3-3H5.25a3 3 0 00-3 3m16.5 0h.008v.008h-.008v-.008zm-3 0h.008v.008h-.008v-.008z" />
                        </svg>
                      </div>
                      <span className="font-medium text-white text-sm">Self-Deploys on Kubernetes</span>
                    </div>
                    <p className="text-xs text-gray-400">Manages its own pods, recovers from failures, scales horizontally. Ran 48 hours autonomously.</p>
                  </div>
                </div>

                {/* Runtime badge */}
                <div className="mt-3 flex items-center justify-center gap-2 text-xs text-gray-500">
                  <svg className="h-3 w-3 text-cyan-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span>Built in Rust · Memory safe · Production grade</span>
                </div>
              </div>
            </div>
          </div>
          <div className="relative -mt-4 lg:col-span-7 lg:mt-0 xl:col-span-6">
            <p className="text-center text-sm font-semibold text-gray-400 lg:text-left">
              Built for developers who think about what happens after the demo
            </p>
            <ul
              role="list"
              className="mx-auto mt-8 flex max-w-xl flex-wrap justify-center gap-x-8 gap-y-4 lg:mx-0 lg:justify-start"
            >
              {[
                ['Rust', 'Memory safe'],
                ['Kubernetes', 'Self-deploying'],
                ['Persona Swarms', 'Scoped access'],
                ['Audit Logs', 'Every action'],
                ['MIT License', 'Your terms'],
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
