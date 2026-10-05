import { GithubAppWorkflowsProvider } from './GithubAppWorkflowsContext'
import { GithubAppWorkflowsView } from './GithubAppWorkflowsView'

export default function GithubAppWorkflowsPage() {
  return (
    <GithubAppWorkflowsProvider>
      <GithubAppWorkflowsView />
    </GithubAppWorkflowsProvider>
  )
}
