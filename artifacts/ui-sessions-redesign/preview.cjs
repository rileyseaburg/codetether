const React = require('react')
const { createRoot } = require('react-dom/client')
const { SessionList } = require('@/app/(dashboard)/dashboard/sessions/components/SessionList')
const { ChatHeader } = require('@/app/(dashboard)/dashboard/sessions/components/ChatHeader')
const { ChatInput } = require('@/app/(dashboard)/dashboard/sessions/components/ChatInput')
const { ChatMessages } = require('@/app/(dashboard)/dashboard/sessions/components/ChatMessages')
const h = React.createElement
const sessions = [
  { id: 'release', title: 'Plan the next release', time: { created: 1788560000000, updated: 1788650000000 } },
  { id: 'onboarding', title: 'Simplify customer onboarding', time: { created: 1788540000000, updated: 1788550000000 } },
  { id: 'review', title: 'Review the authentication flow', time: { created: 1788440000000, updated: 1788540000000 } },
]
const messages = [
  { key: 'one', role: 'user', label: 'You', text: 'Help me plan the next release. What should we focus on first?', createdAt: '2026-09-06T10:00:00Z' },
  { key: 'two', role: 'assistant', label: 'Assistant', text: 'Start with the path customers use every day: **sign in, choose a workspace, and continue a conversation**.\n\nFor this release I suggest:\n\n1. Make the next action obvious.\n2. Keep the conversation readable.\n3. Put advanced controls in settings, not in the way.\n\nWe can ship that as a small, focused update.', createdAt: '2026-09-06T10:00:04Z' },
]
function Preview() {
  const [workspace, setWorkspace] = React.useState('website')
  const [selected, setSelected] = React.useState(sessions[0])
  const [mobileList, setMobileList] = React.useState(false)
  const [draft, setDraft] = React.useState('')
  return h('div', { className: 'grid h-dvh grid-cols-1 overflow-hidden border border-gray-200 bg-white font-sans md:grid-cols-[18rem_minmax(0,1fr)]' },
    h('aside', { className: `${mobileList || !selected ? '' : 'hidden'} min-h-0 border-r border-gray-200 md:block` },
      h(SessionList, { workspaces: [{ id: 'website', name: 'CodeTether website', path: '/fixture', status: 'online' }], sessions: workspace ? sessions : [], selectedWorkspace: workspace, selectedSession: selected, onWorkspaceChange: id => { setWorkspace(id); setSelected(null) }, onSessionSelect: session => { setSelected(session); setMobileList(false) } })),
    h('div', { className: `${mobileList ? 'hidden' : 'flex'} min-h-0 min-w-0 flex-col md:flex` },
      h('div', { className: 'mx-auto flex h-full min-h-0 w-full max-w-4xl flex-col [&_article_.wrap-break-word]:text-base [&_article_.wrap-break-word]:leading-7 [&_section>div.sticky]:border-0 [&_section>div.sticky]:bg-transparent [&_section>div.sticky]:py-1' },
        selected ? h(React.Fragment, null,
          h(ChatHeader, { selectedSession: selected, selectedWorkspace: workspace, selectedWorkspaceName: 'CodeTether website', selectedMode: 'code', selectedModel: 'one', suggestedModels: [], streamConnected: true, streamStatus: 'connected', loading: false, chatItemsCount: 2, showBackButton: true, onBackToSessions: () => setMobileList(true), onModeChange() {}, onModelChange() {}, onResume() {}, onRefresh() {}, onToggleRLMPane() {} }),
          h(ChatMessages, { chatItems: messages, selectedSession: selected, loading: false, loadingMore: false, hasMore: false, totalMessages: 2, error: null, liveDraft: '', awaitingResponse: false, onLoadMore() {} }),
          h(ChatInput, { draftMessage: draft, onDraftChange: setDraft, onSend: () => setDraft(''), hasSession: true, loading: false, actionStatus: null }))
        : h('section', { className: 'flex flex-1 flex-col items-center justify-center px-6 text-center' },
          h('h2', { className: 'text-2xl font-semibold' }, workspace ? 'Choose a session' : 'Choose a workspace'),
          h('p', { className: 'mt-3 max-w-sm text-sm leading-7 text-gray-500' }, 'Choose a workspace from the list. Its sessions will appear here, ready to continue.')))))
}
createRoot(document.getElementById('root')).render(h(Preview))
