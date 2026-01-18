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
            <stop stopColor="#06b6d4" />
            <stop offset="1" stopColor="#06b6d4" stopOpacity="0" />
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
            <stop stopColor="#06b6d4" />
            <stop offset="1" stopColor="#06b6d4" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  )
}

function GitHubIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
    </svg>
  )
}

function DocsIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
    </svg>
  )
}

export function Hero() {
  return (
    <div className="overflow-hidden pt-14 pb-16 sm:pt-24 sm:pb-24 lg:pt-32 lg:pb-32 xl:pb-36 bg-white dark:bg-gray-950">
      <Container>
        <div className="lg:grid lg:grid-cols-12 lg:gap-x-8 lg:gap-y-20">
          <div className="relative z-10 mx-auto max-w-2xl lg:col-span-7 lg:max-w-none lg:pt-6 xl:col-span-6">
            <h1 className="text-3xl font-medium tracking-tight leading-tight text-gray-900 dark:text-white sm:text-4xl lg:text-5xl">
              Your AI. Your Data. <br />
              <span className="text-cyan-600 dark:text-cyan-400">Your Network.</span>
            </h1>
            <p className="mt-6 text-lg text-gray-600 dark:text-gray-300">
              CodeTether brings AI agents to your data—not your data to AI.
              Deploy workers inside secure networks that pull tasks and stream results,
              with zero inbound firewall rules. Enterprise-ready from day one.
            </p>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-4">
              <Button href="https://github.com/rileyseaburg/codetether">
                <GitHubIcon className="h-5 w-5 flex-none" />
                <span className="ml-2.5">Star on GitHub</span>
              </Button>
              <Button
                href="https://github.com/rileyseaburg/codetether/blob/main/README.md"
                variant="outline"
              >
                <DocsIcon className="h-5 w-5 flex-none" />
                <span className="ml-2.5">Read Docs</span>
              </Button>
            </div>
          </div>
          <div className="relative mt-10 sm:mt-20 lg:col-span-5 lg:row-span-2 lg:mt-0 xl:col-span-6">
            <BackgroundIllustration className="absolute top-4 left-1/2 h-[1026px] w-[1026px] -translate-x-1/3 mask-[linear-gradient(to_bottom,white_20%,transparent_75%)] stroke-gray-300/70 dark:stroke-gray-700/50 sm:top-16 sm:-translate-x-1/2 lg:-top-16 lg:ml-12 xl:-top-14 xl:ml-0" />
            <div className="-mx-4 h-[448px] px-9 sm:mx-0 lg:absolute lg:-inset-x-10 lg:-top-10 lg:-bottom-20 lg:h-auto lg:px-0 lg:pt-10 xl:-bottom-32">
              <div className="mx-auto max-w-[500px] rounded-2xl bg-gray-900 p-4 shadow-2xl ring-1 ring-white/10">
                <div className="flex items-center gap-2 border-b border-gray-700 pb-3">
                  <div className="h-3 w-3 rounded-full bg-red-500" />
                  <div className="h-3 w-3 rounded-full bg-yellow-500" />
                  <div className="h-3 w-3 rounded-full bg-green-500" />
                  <span className="ml-2 text-sm text-gray-400">codetether-cli</span>
                </div>
                <div className="mt-4 font-mono text-sm leading-relaxed break-words">
                  <p className="text-green-400">$ codetether worker start --env hospital-vpc</p>
                  <p className="mt-2 text-gray-400">Initializing Worker in secure VPC...</p>
                  <p className="text-cyan-400">✓ Pull-based worker started</p>
                  <p className="text-cyan-400">✓ Connected to CodeTether server (outbound)</p>
                  <p className="text-cyan-400">✓ Zero inbound ports required</p>
                  <p className="mt-2 text-gray-400"># Polling for tasks...</p>
                  <p className="text-yellow-400">&gt; New task: analyze_patient_records()</p>
                  <p className="mt-2 text-gray-400"># Processing locally (data never leaves VPC)</p>
                  <p className="text-green-400">✓ Task complete. Streaming result...</p>
                </div>
              </div>
            </div>
          </div>
          <div className="relative -mt-4 lg:col-span-7 lg:mt-0 xl:col-span-6">
            <p className="text-center text-sm font-semibold text-gray-900 dark:text-white lg:text-left">
              Built with industry-leading technologies
            </p>
            <ul
              role="list"
              className="mx-auto mt-8 flex max-w-xl flex-wrap justify-center gap-x-10 gap-y-8 lg:mx-0 lg:justify-start"
            >
              {[
                ['RLM', '∞'],
                ['Zero Trust', '🔐'],
                ['A2A Protocol', '🔗'],
                ['Pull Architecture', '⬇️'],
                ['Kubernetes', '☸️'],
                ['Keycloak SSO', '🛡️'],
                ['HIPAA Ready', '🏥'],
                ['On-Prem', '🏢'],
              ].map(([name, emoji]) => (
                <li key={name} className="flex items-center gap-2">
                  <span className="text-2xl">{emoji}</span>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{name}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Container>
    </div>
  )
}
