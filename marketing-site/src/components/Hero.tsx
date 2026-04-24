'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'

const metrics = [
  { value: '60+', label: 'registered tool IDs' },
  { value: '∞', label: 'workspace context via RLM' },
  { value: '11', label: 'release targets' },
]

const trust = [
  'Rust-native runtime',
  'OKR → PRD → Ralph',
  'Swarm orchestration',
  'MCP + A2A',
  'OPA RBAC',
]

const pipeline = [
  { step: '01', title: 'Objective', detail: 'Capture the outcome, owner, constraints, and success metric.' },
  { step: '02', title: 'PRD', detail: 'Generate stories, acceptance criteria, dependencies, and quality gates.' },
  { step: '03', title: 'Ralph', detail: 'Iterate in fresh contexts, edit real files, test, and commit.' },
  { step: '04', title: 'Control', detail: 'Stream events, enforce policy, audit tools, and route workers.' },
]

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" {...props}>
      <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
    </svg>
  )
}

function ControlPlaneCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.25 }}
      className="relative mx-auto mt-14 max-w-2xl lg:mt-0"
    >
      <div className="absolute -inset-6 rounded-[2rem] bg-cyan-500/20 blur-3xl" />
      <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.06] shadow-2xl shadow-cyan-950/40 backdrop-blur-xl">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-red-400" />
            <span className="h-3 w-3 rounded-full bg-yellow-400" />
            <span className="h-3 w-3 rounded-full bg-green-400" />
          </div>
          <span className="rounded-full bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-200 ring-1 ring-cyan-300/20">
            live agent run
          </span>
        </div>

        <div className="grid gap-0 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="border-b border-white/10 p-5 lg:border-r lg:border-b-0">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200/80">Objective</p>
            <h3 className="mt-3 text-xl font-semibold text-white">Ship GitHub OAuth with policy gates</h3>
            <div className="mt-5 space-y-3 text-sm text-gray-300">
              {pipeline.map((item) => (
                <div key={item.step} className="rounded-2xl border border-white/10 bg-gray-950/50 p-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-400/10 text-xs font-bold text-cyan-200">
                      {item.step}
                    </span>
                    <div>
                      <p className="font-semibold text-white">{item.title}</p>
                      <p className="mt-1 text-xs leading-5 text-gray-400">{item.detail}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="p-5">
            <div className="rounded-2xl bg-gray-950 p-4 font-mono text-xs leading-6 text-gray-300 ring-1 ring-white/10">
              <p><span className="text-cyan-300">$</span> codetether go "add OAuth login"</p>
              <p className="mt-3 text-gray-500">creating OKR…</p>
              <p><span className="text-green-300">✓</span> objective: secure social sign-in</p>
              <p><span className="text-green-300">✓</span> PRD: 5 stories, 18 acceptance criteria</p>
              <p><span className="text-green-300">✓</span> swarm: security + docs + tester</p>
              <p><span className="text-yellow-300">↻</span> ralph: implementing story 4/5</p>
              <p><span className="text-cyan-300">→</span> policy: OPA authz.rego passed</p>
              <p><span className="text-cyan-300">→</span> browser: replayed /api/session smoke test</p>
            </div>

            <div className="mt-5 grid grid-cols-3 gap-3">
              {metrics.map((metric) => (
                <div key={metric.label} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-center">
                  <div className="text-2xl font-bold text-white">{metric.value}</div>
                  <div className="mt-1 text-[11px] leading-4 text-gray-400">{metric.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export function Hero() {
  return (
    <section className="relative isolate overflow-hidden bg-gray-950 pt-32 pb-20 sm:pt-36 lg:pt-40 lg:pb-28">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_32rem),radial-gradient(circle_at_80%_20%,rgba(59,130,246,0.16),transparent_28rem),linear-gradient(to_bottom,#030712,#020617)]" />
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,rgba(255,255,255,0.06)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.06)_1px,transparent_1px)] bg-[size:44px_44px] opacity-20" />

      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 sm:px-6 lg:grid-cols-[1.02fr_0.98fr] lg:px-8">
        <div className="mx-auto max-w-3xl text-center lg:mx-0 lg:text-left">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1.5 text-xs font-medium text-cyan-100"
          >
            <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_20px_rgba(103,232,249,0.9)]" />
            v4.5.7 · Agent runtime today, control plane next
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.08 }}
            className="mt-8 text-5xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl"
          >
            The control plane for{' '}
            <span className="bg-gradient-to-r from-cyan-200 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
              autonomous engineering
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.16 }}
            className="mt-6 text-lg leading-8 text-gray-300 sm:text-xl"
          >
            CodeTether turns objectives into PRDs, coordinates Ralph and specialized swarms,
            edits real repositories, controls browsers and infrastructure, and keeps every tool call governed by policy.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.24 }}
            className="mt-10 flex flex-col items-center gap-4 sm:flex-row lg:justify-start"
          >
            <Link
              href="/register"
              className="inline-flex items-center justify-center rounded-xl bg-cyan-300 px-6 py-3 text-base font-semibold text-gray-950 shadow-xl shadow-cyan-500/20 transition hover:bg-cyan-200"
            >
              Start building free
            </Link>
            <a
              href="https://github.com/rileyseaburg/codetether"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-base font-semibold text-white transition hover:bg-white/10"
            >
              View the agent runtime
            </a>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.34 }}
            className="mt-8 flex flex-wrap justify-center gap-x-5 gap-y-3 text-sm text-gray-400 lg:justify-start"
          >
            {trust.map((item) => (
              <span key={item} className="inline-flex items-center gap-2">
                <CheckIcon className="h-4 w-4 text-cyan-300" />
                {item}
              </span>
            ))}
          </motion.div>
        </div>

        <ControlPlaneCard />
      </div>
    </section>
  )
}
