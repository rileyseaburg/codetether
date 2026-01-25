# CodeTether Development Guidelines

## Brand & Design System

### Color Palette

#### Primary Brand Color
- **Cyan** - Primary accent and brand identity
  - Light: `cyan-300`, `cyan-400`, `cyan-500`
  - Medium: `cyan-600`
  - Dark: `cyan-900`, `cyan-950`
  - Semi-transparent: `cyan-500/20`, `cyan-950/40`, `cyan-950/50`, `cyan-900/30`
  - Uses: Hero highlights, buttons, badges, accents, call-to-actions

#### Background Colors
- **Grayscale** - All surfaces and backgrounds
  - Light mode: `gray-50`, `gray-100`, `gray-200`, `gray-300`, `gray-400`, `gray-500`, `gray-600`, `gray-700`, `gray-800`, `gray-900`
  - Dark mode: `gray-950` (main), `blue-950` (alternative dark)
  - Semi-transparent: `gray-900/50`, `gray-800/50`, `gray-900/20`, `gray-900/30`

#### Secondary/Accent Colors
- **White** - Text and cards in dark mode
  - `text-white`, `bg-white`
- **Gray text** - All body text
  - `text-gray-300`, `text-gray-400`, `text-gray-500`, `text-gray-600`
  - `dark:text-gray-400`, `dark:text-gray-500`, `dark:text-gray-600`

#### State Colors
- **Green/Emerald** - Success states
  - Light: `emerald-50`, `emerald-400`
  - Dark: `emerald-600`, `emerald-700`
- **Orange** - Warnings
  - Light: `orange-500`, `orange-600`
- **Red** - Errors
  - Light: `red-100`, `red-500`
  - Dark: `red-700`

#### Voice UI State Colors
- **Idle:** `gray-400` to `gray-600`
- **Connected:** `blue-400` to `blue-600`
- **Speaking:** `green-400` to `green-600`
- **Listening:** `yellow-400` to `yellow-600`
- **Processing:** `purple-500` to `violet-400`
- **Thinking:** `purple-500` (limited use in voice UI)

#### Common Gradients
- `from-cyan-500 to-cyan-500` - Brand accents
- `from-cyan-950/40 to-gray-900` - Section backgrounds
- `from-cyan-600 to-cyan-800` - Hero backgrounds

### Design Tokens Summary

| Category | Primary | Dark Mode/Alt |
|----------|---------|----------------|
| Brand | Cyan | Cyan-900, Cyan-950 |
| Background | Gray-50/White | Gray-950, Blue-950 |
| Text | Gray-300/400 | Gray-400/500/600 |
| Success | Emerald-400/600 | |
| Warning | Orange-500/600 | |
| Error | Red-100/500/700 | |

---

### Component Styling Patterns

#### Input Fields
- Default border: `border-gray-300` (light) / `dark:border-gray-600`
- Focus: `focus:ring-2 focus:ring-cyan-500`
- Background: `bg-white` / `dark:bg-gray-900`
- Text: `text-gray-900` / `dark:text-white`

#### Buttons
- Primary (Cyan): `bg-cyan-500 hover:bg-cyan-400 text-white`
- Secondary: `bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300`
- Outline: `border-gray-200 text-gray-300`

#### Cards/Panels
- Background: `bg-white` / `dark:bg-gray-800`
- Border: `border-gray-200` / `dark:border-gray-700`
- Shadow: `shadow-2xl` for elevated elements
- Radius: `rounded-lg`, `rounded-xl`, `rounded-2xl`

#### Badges/Tags
- Cyan accent: `bg-cyan-500/20 text-cyan-400`
- Gray neutral: `bg-gray-800 px-2 py-1 text-xs`

#### Messages/Chat
- User: `bg-cyan-500 text-white`
- Assistant: `bg-white dark:bg-gray-800`
- Error: `bg-red-100 dark:bg-red-900/30 text-red-700`

---

## API Calls - Type-Safe SDK from OpenAPI

### Auto-Generated Type-Safe API Client

**All API communication MUST use the auto-generated SDK** from `@/lib/api` instead of direct `fetch()` calls.

#### How It Works

1. **OpenAPI spec** is fetched from `https://api.codetether.run/openapi.json`
2. **@hey-api/openapi-ts** generates TypeScript types and SDK functions
3. **Environment-aware** base URL configured in `src/lib/api/index.ts`

#### Generated Files Location
```
src/lib/api/
├── index.ts              # Environment-aware client setup + re-exports
├── generated/
│   ├── client.gen.ts     # Base client configuration
│   ├── sdk.gen.ts        # Type-safe API functions
│   ├── types.gen.ts      # TypeScript types from OpenAPI
│   └── index.ts          # Barrel exports
```

#### Usage Pattern
```typescript
// Import from @/lib/api (NOT from generated directly)
import { listWorkersV1OpencodeWorkersGet, createRalphRunV1RalphRunsPost } from '@/lib/api'

// Use type-safe SDK functions
const { data: workers } = await listWorkersV1OpencodeWorkersGet()

const { data } = await createRalphRunV1RalphRunsPost({
  body: { prd: {...}, max_iterations: 10 }
})
```

#### Regenerating the SDK
```bash
cd marketing-site
npm run generate:api
```

Run this when:
- API endpoints change
- New routes are added to the backend
- Types need to be updated

#### Environment Configuration
The client automatically selects the base URL:
- `NEXT_PUBLIC_API_URL` env var (if set)
- `http://localhost:8000` in development
- `https://api.codetether.run` in production

### Task Completion Rule

**Critical**: You cannot claim a task is complete if:
- You introduced or left any direct `fetch()` calls that should use the SDK
- You used `fetch()` instead of the generated SDK functions
- TypeScript errors exist in API calls

Before marking a task complete, verify:
1. All API calls use SDK functions from `@/lib/api`
2. No raw `fetch()` calls for API endpoints
3. TypeScript errors are resolved
4. The code compiles and runs

### Next Steps (TODO)

- [ ] Add pre-commit hook to regenerate SDK if openapi.json changed
- [ ] Set up CI to fail if SDK is out of date
- [ ] Add React Query integration for caching/mutations
- [ ] Create custom hooks that wrap SDK calls with loading/error states

---

## SRP Modular Cohesion - 50 Line Rule

When developing components for the CodeTether platform, follow these architectural principles:

### 1. Single Responsibility Principle (SRP)
Each component should have **one reason to change** and handle **one well-defined duty**:
- ✅ **Focus**: UI rendering, data fetching, or event handling (not all three)
- ✅ **Coherence**: Related functionality grouped together
- ❌ **Avoid**: Components that do multiple unrelated things

### 2. Modularity
Components should be **independent and reusable**:
- Standalone with clear interfaces (props)
- No hidden dependencies or side effects
- Can be used in multiple contexts without modification

### 3. Cohesion
Group related functionality together:
- UI elements in one folder (`components/ui/`)
- Custom hooks and state logic in separate files
- API calls isolated from components

### 4. 50 Lines Max
**No component should exceed 50 lines of code**

This ensures components are:
- **Maintainable** - Easy to understand at a glance
- **Testable** - Simple to unit test
- **Composable** - Building blocks for larger features

### 5. Storybook-Style
Components should be **self-contained and reusable**:
- Clear prop interfaces with TypeScript types
- Work independently without complex parent requirements
- Can be dropped into Storybook for isolated development

---

## Example Refactoring

**Before (642 lines - violates SRP):**
```tsx
// AIPRDBuilder.tsx - One huge component
function AIPRDBuilder() {
    // 642 lines of mixed concerns:
    // - UI rendering
    // - Chat state management
    // - API calls
    // - Message handling
    // - Error handling
    // - Everything in one file
}
```

**After (238 lines - follows SRP):**
```
components/
├── ui/
│   ├── ChatIcons.tsx (17 lines) - Icons only
│   ├── LoadingDots.tsx (9 lines) - Animation only
│   ├── ChatMessage.tsx (23 lines) - Message bubble
│   ├── ChatInput.tsx (40 lines) - Input + send button
│   ├── QuickPrompts.tsx (23 lines) - Prompt chips
│   ├── ModalHeader.tsx (39 lines) - Header
│   ├── PRDCard.tsx (21 lines) - PRD display card
│   ├── PRDPreviewPanel.tsx (36 lines) - Generated PRD preview
│   └── ModelSelector.tsx (47 lines) - Model selection
├── AIPRDBuilder.tsx (58 lines) - Main layout/orchestration
├── useAIPRDChat.ts (108 lines) - Chat state + hooks
└── prd-api.ts (72 lines) - API helpers
```

---

## Checklist

Before committing code, verify:

- [ ] Each file is **≤ 50 lines** (exceptions only for hook/logic files)
- [ ] Component has **single responsibility**
- [ ] Props have **clear TypeScript interfaces**
- [ ] No hidden dependencies or side effects
- [ ] Component is **reusable across contexts**
- [ ] Logic separated from UI (hooks, utilities, API)

---

## Benefits

Following these rules results in:
- **Faster development** - Smaller components are quicker to write and debug
- **Easier collaboration** - Team members can work on different components without conflicts
- **Better testing** - Isolated components are trivial to unit test
- **Simpler maintenance** - Changes affect small, focused areas
- **Storybook ready** - Components can be independently documented and tested

---

## Deployment

### Marketing Site Deployment

The marketing site (`marketing-site/`) deploys to **Kubernetes** using blue-green deployment.

#### Deployment Command
```bash
# Full build and deploy
make codetether-full-deploy

# Or directly use the script
./scripts/bluegreen-marketing.sh deploy
```

#### What It Does
1. Builds Docker image: `us-central1-docker.pkg.dev/spotlessbinco/codetether/codetether-marketing:latest`
2. Pushes to Google Artifact Registry
3. Deploys to Kubernetes namespace `a2a-server`
4. Uses blue-green deployment (alternates between `blue` and `green` slots)
5. Runs health checks before switching traffic
6. Scales down old deployment after successful switch

#### Other Commands
```bash
# Check deployment status
./scripts/bluegreen-marketing.sh status

# Rollback to previous slot
./scripts/bluegreen-marketing.sh rollback
```

#### NEVER Deploy To
- **Cloud Run** - Do not use `gcloud run deploy` for the marketing site
- **AWS** - All infrastructure is self-hosted

#### Infrastructure
- **Hosting**: Self-hosted Kubernetes on Proxmox
- **Registry**: `us-central1-docker.pkg.dev/spotlessbinco/codetether/` (GCP Artifact Registry for images only)
- **Kubernetes Namespace**: `a2a-server`
- **Service Name**: `codetether-marketing`
- **Deployments**: `codetether-marketing-blue`, `codetether-marketing-green`
