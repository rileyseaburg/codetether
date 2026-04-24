# Marketing Site Refactor Plan

## Executive summary

The `marketing-site` app has a strong product surface and modern stack: Next.js App Router, React 19, Tailwind CSS v4, Headless UI, Framer Motion, Playwright, and generated API clients. The main opportunity is structural: many pages and sections are implemented as large route-local files or top-level one-off components, with repeated styling, duplicated widgets, embedded data, and inconsistent client/server boundaries.

This plan proposes turning the app into a composable design-system-driven marketing and dashboard frontend with reusable primitives, section templates, page-specific feature modules, and clearer server/client splits.

## Audit findings

### Current stack and layout

- Framework: Next.js `^16.1.0` App Router.
- React: `^19.2.3`.
- Styling: Tailwind CSS v4 via `src/styles/tailwind.css`.
- UI helpers: `clsx`, Headless UI, Framer Motion, Lucide, Recharts.
- App groups:
  - `src/app/(main)` for public marketing pages.
  - `src/app/(auth)` for login/register.
  - `src/app/(dashboard)` for authenticated dashboard.
  - `src/app/api` for Next route handlers.

### Size and organization signals

- `src` contains roughly 72k lines, inflated by generated API/grpc code.
- There are 98 files marked `'use client'`, suggesting too much client-side rendering by default.
- Top-level `src/components` contains 38 files mixing public marketing sections, dashboard widgets, auth wrappers, chat, and primitive UI.
- Large route/page files are common:
  - `src/app/(dashboard)/dashboard/page.tsx` ~2,618 lines.
  - `src/app/(dashboard)/dashboard/cognition/page.tsx` ~1,501 lines.
  - `src/app/(dashboard)/dashboard/billing/page.tsx` ~1,178 lines.
  - `src/app/(dashboard)/dashboard/tasks/page.tsx` ~919 lines.
  - `src/app/(dashboard)/dashboard/ads/page.tsx` ~895 lines.
  - `src/app/(main)/benchmarks/page.tsx` ~653 lines.
  - `src/components/RalphDemo.tsx` ~676 lines.
  - `src/components/Pricing.tsx` ~535 lines.

### Immediate correctness/UX issues

1. **`ChatWidget` is rendered twice on the home page.**
   - Global root layout renders it in `src/app/layout.tsx`.
   - Home page also renders it in `src/app/(main)/page.tsx`.
   - This can duplicate network work, floating UI, event listeners, and hydration cost.

2. **Main nav anchor mismatch.**
   - `Header` links `#features`, but `PrimaryFeatures` uses `id="how-it-works"`.
   - This makes the primary nav less reliable and hurts perceived polish.

3. **Marketing sections are mostly client components.**
   - `Hero`, `PrimaryFeatures`, `Pricing`, `Header`, and others use `'use client'` even where only small subtrees require interactivity.
   - This increases JS shipped to visitors and makes section content harder to stream/cache as static server-rendered markup.

4. **Root document constrains viewport height.**
   - `html` and `body` have inline `maxHeight: '100vh'` in `src/app/layout.tsx`.
   - That can create scroll/overflow issues on long public and dashboard pages.

5. **Generated and backup artifacts live beside authored code.**
   - Examples: `ChatWidget.tsx.bak`, `PrimaryFeatures.tsx.bak`, many `openapi-ts-error-*.log`, `tsconfig.tsbuildinfo`, `test-results`.
   - These should be cleaned, gitignored, or moved to generated/build artifact locations.

## Refactor goals

1. **Componentize by domain, not by accident.** Public marketing, dashboard, auth, API clients, and shared UI should be separated.
2. **Move repeated UI into reusable primitives.** Cards, buttons, badges, section headers, metric tiles, code windows, pricing cards, tabs, empty states, and dashboard shells should be standard.
3. **Prefer server components for static content.** Only interactive islands should be client components.
4. **Centralize content/data configuration.** Marketing copy and pricing tables should be data objects or CMS-ready config, not embedded across JSX.
5. **Improve visual consistency.** Establish design tokens for color, spacing, typography, surfaces, shadows, radii, and motion.
6. **Improve accessibility and performance.** Fix nav targets, focus states, reduced-motion behavior, loading strategy, metadata, and duplicate widgets.

## Proposed directory structure

```text
src/
  app/
    (main)/
      page.tsx
      benchmarks/page.tsx
      investors/page.tsx
    (auth)/
    (dashboard)/
    api/
  components/
    ui/                  # design primitives only
      button.tsx
      card.tsx
      badge.tsx
      container.tsx
      section.tsx
      tabs.tsx
      code-window.tsx
      metric-card.tsx
      dialog.tsx
      skeleton.tsx
    layout/
      site-header.tsx
      site-footer.tsx
      dashboard-shell.tsx
      mobile-nav.tsx
    marketing/
      home/
        hero.tsx
        social-proof.tsx
        feature-tabs.tsx
        ralph-demo.tsx
        rlm-explainer.tsx
        use-cases.tsx
        roadmap.tsx
        pricing.tsx
        faq.tsx
        contact.tsx
      benchmarks/
      investors/
    dashboard/
      nav/
      cards/
      charts/
      tables/
      modules/
        workspaces/
        workers/
        tasks/
        billing/
        ralph/
        cognition/
        ads/
  content/
    marketing.ts
    pricing.ts
    nav.ts
    faqs.ts
    features.ts
  hooks/
  lib/
  styles/
```

## Componentization plan

### 1. Shared UI primitives

Create or normalize these primitives under `src/components/ui`:

- `Button`: replace ad-hoc `Link`/`button` Tailwind strings with variants: `primary`, `secondary`, `ghost`, `outline`, `destructive`.
- `Container`: keep the existing primitive, but make it the only horizontal layout wrapper.
- `Section`: standard vertical padding, background variants, anchor/id support.
- `SectionHeader`: eyebrow, title, description, alignment, max width.
- `Card`: surface variants for light/dark, glass, bordered, elevated.
- `Badge`: status and product-label pills.
- `CodeWindow`: terminal chrome + syntax/code block treatment currently duplicated in `Hero` and `PrimaryFeatures`.
- `MetricCard`: value/label/trend primitive for hero metrics and dashboard stats.
- `FeatureCard`: icon, title, description, CTA optional.
- `PricingCard`: plan rendering independent from pricing data.
- `Skeleton`: replace local `SectionSkeleton` with reusable loading states.

### 2. Marketing content modules

Move static arrays out of components:

- `Hero.metrics`, `Hero.trust`, and `Hero.pipeline` → `src/content/marketing.ts`.
- `PrimaryFeatures.features` → `src/content/features.ts`.
- `Pricing.plans` → `src/content/pricing.ts`.
- `Faqs` items → `src/content/faqs.ts`.
- Header/footer nav → `src/content/nav.ts`.

This makes copy review and pricing edits safer and prepares the site for a CMS or localization later.

### 3. Marketing section decomposition

Refactor large section files into smaller subcomponents:

- `Hero.tsx`
  - `HeroCopy`
  - `HeroActions`
  - `TrustList`
  - `ControlPlanePreview`
  - `PipelineStepCard`
  - `MetricStrip`
- `PrimaryFeatures.tsx`
  - `FeatureTabs.client.tsx`
  - `FeatureTabTrigger`
  - `FeaturePanel`
  - `FeatureMobileStack`
- `Pricing.tsx`
  - `PricingSection`
  - `BillingToggle.client.tsx`
  - `PricingCard`
  - `PlanFeatureList`
  - `CheckoutButton.client.tsx`
- `RalphDemo.tsx`
  - split into copy, timeline, terminal/log stream, and outcome cards.
- `Benchmarks` and comparison pages
  - move table/chart primitives into shared modules and keep page files as orchestration only.

Target: route `page.tsx` files should mostly compose sections and stay under ~150 lines. Section components should generally stay under ~250 lines. Larger interactive experiences should be split into colocated components/hooks.

### 4. Server/client boundary cleanup

Use server components by default:

- Convert static marketing sections to server components.
- Extract interactive parts into `*.client.tsx` components:
  - Header mobile menu and scroll state.
  - Framer Motion animated wrappers.
  - Feature tabs.
  - Pricing checkout state/session logic.
  - Chat widget.
- Consider replacing some Framer Motion page-load animations with CSS `@starting-style`, Tailwind animation utilities, or a tiny `MotionProvider` island.

Example pattern:

```tsx
// hero.tsx - server component
export function Hero() {
  return (
    <Section variant="dark">
      <HeroCopy />
      <HeroPreviewClient />
    </Section>
  )
}
```

### 5. Dashboard componentization

Dashboard files are the largest maintainability risk. Introduce a dashboard component system:

- `DashboardShell`: sidebar, topbar, mobile nav, auth state.
- `DashboardPageHeader`: title, description, action slot, breadcrumbs.
- `StatGrid` / `StatCard`.
- `DataTable` wrapper for consistent loading, empty, error, and pagination states.
- `StatusBadge` and `HealthIndicator`.
- `CommandPanel` / `TerminalPanel`.
- `ResourceCard` for workspaces/workers/tasks.
- Route-specific modules under `src/components/dashboard/modules/<feature>`.

Refactor route pages incrementally:

1. `dashboard/page.tsx` from ~2,600 lines into overview modules.
2. `billing/page.tsx` into plan cards, invoices, usage, checkout state.
3. `tasks/page.tsx` into filters, task list, task detail, task actions.
4. `cognition/page.tsx`, `ads/page.tsx`, and `analytics/page.tsx` into chart/card modules.

### 6. Visual/UI technique upgrades

#### Design system tokens

Extend `tailwind.css` with semantic tokens instead of raw gray/cyan usage everywhere:

- `--color-background`
- `--color-foreground`
- `--color-surface`
- `--color-surface-elevated`
- `--color-border`
- `--color-muted`
- `--color-brand`
- `--color-brand-foreground`
- `--shadow-card`
- `--shadow-glow`

Then expose Tailwind utilities/classes through component variants.

#### Better layout rhythm

- Standardize section padding: `py-20 sm:py-28 lg:py-32` for major marketing sections.
- Standardize max-widths: copy `max-w-2xl`, content `max-w-7xl`, narrow legal `max-w-3xl`.
- Use `SectionHeader` everywhere for consistent hierarchy.

#### Modern hero improvements

- Keep the dark command/control-plane direction, but make the preview feel product-real:
  - Add a segmented status rail: `OKR`, `PRD`, `Ralph`, `Tests`, `Review`.
  - Show progressive completion states with subtle motion.
  - Add a policy/audit strip to reinforce enterprise trust.
- Add a lightweight product screenshot/video placeholder when a real dashboard shot is available.

#### Card and surface consistency

- Replace one-off `rounded-3xl border bg-white/[0.06] shadow-*` strings with `Card` variants.
- Use consistent icon containers, badge sizing, border opacity, and hover states.
- Use subtle gradients sparingly; make brand cyan the action color, not every surface.

#### Motion and interaction

- Respect `prefers-reduced-motion`.
- Avoid animating layout-heavy properties like `height` where possible; use transform/opacity or Headless UI transitions.
- Add hover/focus microinteractions on cards and CTAs using shared variants.

#### Accessibility

- Fix anchor targets and add visible focus styles to every CTA/nav item.
- Ensure mobile menu has `aria-expanded`, `aria-controls`, and closes on route change/Escape.
- Ensure icon-only GitHub link has an accessible label.
- Use semantic sections with `aria-labelledby` where headings exist.
- Check contrast for gray-on-dark text and cyan-on-light CTAs.

#### Performance

- Remove duplicate `ChatWidget` render.
- Lazy-load ChatWidget only after idle, user intent, or on marketing routes where it is needed.
- Audit Framer Motion usage and client component spread.
- Move generated API clients out of primary chunks when possible; import route-specific clients only where used.
- Use `next/image` for any raster images/screenshots.
- Add bundle analyzer scripts using the existing `@next/bundle-analyzer` dependency.

## Recommended implementation phases

### Phase 0: quick fixes

- Remove `ChatWidget` from `src/app/(main)/page.tsx` or from the root layout; prefer one controlled placement.
- Fix nav anchor mismatch: either change Header `#features` to `#how-it-works` or rename section id to `features`.
- Remove `maxHeight: '100vh'` inline styles from root `html`/`body` unless there is a specific dashboard-only reason.
- Delete or gitignore `.bak`, `openapi-ts-error-*.log`, `tsconfig.tsbuildinfo`, and stale `test-results` artifacts.

### Phase 1: design primitives

- Create the `ui` primitives listed above.
- Replace ad-hoc buttons/cards/containers in marketing sections.
- Add semantic design tokens to Tailwind theme.
- Add Storybook-like documentation page or internal `/dashboard/design-system` route if Storybook is too heavy.

### Phase 2: marketing home refactor

- Move content arrays into `src/content`.
- Split `Hero`, `PrimaryFeatures`, `Pricing`, and `RalphDemo`.
- Convert static section shells to server components.
- Keep only tabs, checkout, menu, and chat as client islands.

### Phase 3: dashboard shell and modules

- Extract `DashboardShell` and navigation data from `src/app/(dashboard)/layout.tsx`.
- Create shared dashboard cards, status badges, stat grids, tables, and page headers.
- Refactor the largest dashboard pages one at a time.

### Phase 4: polish and validation

- Run Playwright across marketing, auth, and dashboard smoke paths.
- Add visual regression screenshots for home, pricing, register, dashboard overview, and mobile nav.
- Run bundle analyzer and compare JS shipped before/after.
- Validate Lighthouse/Core Web Vitals on public pages.

## Suggested acceptance criteria

- Home page has exactly one ChatWidget instance.
- Public marketing nav anchors all scroll to existing sections.
- No top-level marketing section file exceeds ~300 lines after refactor.
- Route page files primarily compose components and avoid embedded datasets.
- Static marketing sections render as server components unless they need interactivity.
- Shared `Button`, `Card`, `Section`, `SectionHeader`, `Badge`, and `CodeWindow` are used across the home page.
- Dashboard layout/navigation data is no longer embedded in one massive layout file.
- Playwright smoke tests pass for home, login/register, and dashboard access states.
- Bundle analyzer shows reduced first-load JS for `/` compared with the current implementation.

## Priority checklist

1. Fix duplicate ChatWidget.
2. Fix marketing nav section IDs.
3. Remove root `maxHeight: 100vh` constraint or scope it to dashboard if needed.
4. Introduce `Section`, `SectionHeader`, `Card`, `Badge`, `CodeWindow`, and improved `Button` primitives.
5. Move marketing copy/pricing/nav data into `src/content`.
6. Split `Hero`, `PrimaryFeatures`, `Pricing`, and `RalphDemo`.
7. Convert static marketing sections to server components with small client islands.
8. Extract dashboard shell/navigation and begin breaking down large dashboard pages.
