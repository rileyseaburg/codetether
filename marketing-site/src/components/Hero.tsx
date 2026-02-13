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
              <span className="text-xs font-medium text-cyan-400">v1.4.2 Shipped</span>
              <span className="text-xs text-gray-400">Zapier · Ralph · RLM · A2A Protocol · Agent Discovery</span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight leading-tight text-white sm:text-4xl lg:text-5xl">
              Autonomous AI Development<br />
              <span className="text-cyan-400">with Infinite Context.</span>
            </h1>
            <p className="mt-6 text-lg text-gray-300">
              <span className="text-pink-400 font-semibold">RLM</span> breaks the context window barrier. <span className="text-cyan-300 font-semibold">Ralph</span> implements entire PRDs autonomously. A2A Protocol compliant. Zapier integrated.
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
              <p className="text-xs text-gray-400 font-medium mb-4">Shipped in v1.4.x — new capabilities now live:</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="rounded-lg bg-gradient-to-b from-pink-950/30 to-gray-900/50 p-3 border border-pink-500/20">
                  <p className="text-sm text-white font-medium">RLM</p>
                  <p className="text-xs text-gray-400 mt-1">10M+ token context. 91% accuracy.</p>
                </div>
                <div className="rounded-lg bg-gray-900/50 p-3 border border-gray-800">
                  <p className="text-sm text-white font-medium">Ralph</p>
                  <p className="text-xs text-gray-400 mt-1">PRD → code, autonomous. MCP-driven.</p>
                </div>
                <div className="rounded-lg bg-gray-900/50 p-3 border border-gray-800">
                  <p className="text-sm text-white font-medium">Zapier</p>
                  <p className="text-xs text-gray-400 mt-1">18 components. Triggers, actions, searches.</p>
                </div>
                <div className="rounded-lg bg-gray-900/50 p-3 border border-gray-800">
                  <p className="text-sm text-white font-medium">A2A Protocol</p>
                  <p className="text-xs text-gray-400 mt-1">v0.3 compliant. Agent discovery.</p>
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
                  {/* RLM - Highlight as the key differentiator */}
                  <div className="rounded-xl bg-gradient-to-r from-pink-950/50 to-gray-800 p-4 border border-pink-500/20">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="h-8 w-8 rounded-lg bg-pink-500/20 flex items-center justify-center">
                        <span className="text-pink-400 text-lg">♾️</span>
                      </div>
                      <span className="font-medium text-white text-sm">RLM — Infinite Context</span>
                    </div>
                    <p className="text-xs text-gray-400">10M+ tokens. 91% accuracy. MIT CSAIL research-backed.</p>
                  </div>

                  {/* Ralph - Autonomous dev loop */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                        <span className="text-cyan-400 text-lg">🔄</span>
                      </div>
                      <span className="font-medium text-white text-sm">Ralph — Autonomous Dev</span>
                    </div>
                    <p className="text-xs text-gray-400">PRD → implement → test → commit → repeat. Zero human intervention.</p>
                  </div>

                  {/* Integration capabilities */}
                  <div className="rounded-xl bg-gray-800 p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                        <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                      </div>
                      <span className="font-medium text-white text-sm">Integration Ready</span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-400">Zapier</span>
                        <span className="text-cyan-400 font-medium">18 components</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-400">MCP Tools</span>
                        <span className="text-cyan-400 font-medium">29 tools</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-400">A2A Protocol</span>
                        <span className="text-cyan-400 font-medium">v0.3 compliant</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Runtime badge */}
                <div className="mt-3 flex items-center justify-center gap-2 text-xs text-gray-500">
                  <svg className="h-3 w-3 text-cyan-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span>Built in Rust · A2A Protocol · Production Ready</span>
                </div>
              </div>
            </div>
          </div>
          <div className="relative -mt-4 lg:col-span-7 lg:mt-0 xl:col-span-6">
            <p className="text-center text-sm font-semibold text-gray-400 lg:text-left">
              Built for developers who ship, not just demo
            </p>
            <ul
              role="list"
              className="mx-auto mt-8 flex max-w-xl flex-wrap justify-center gap-x-8 gap-y-4 lg:mx-0 lg:justify-start"
            >
              {[
                ['RLM', '10M+ tokens'],
                ['Ralph', 'Autonomous dev'],
                ['Zapier', '18 components'],
                ['A2A', 'Protocol v0.3'],
                ['MIT License', 'Open source'],
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
