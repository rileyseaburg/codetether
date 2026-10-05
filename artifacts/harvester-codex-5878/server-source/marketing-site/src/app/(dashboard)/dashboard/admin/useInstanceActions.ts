import { useCallback, useState } from 'react'
import { useSession } from 'next-auth/react'
import {
  suspendInstanceV1AdminInstancesNamespaceSuspendPost,
  resumeInstanceV1AdminInstancesNamespaceResumePost,
  deleteInstanceV1AdminInstancesNamespaceDelete,
} from '@/lib/api'

export function useInstanceActions(onRefresh: () => void) {
  const { data: session } = useSession()
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const token = (session as any)?.accessToken

  const headers = token ? { Authorization: `Bearer ${token}` } : undefined

  const suspendInstance = useCallback(async (tenantId: string) => {
    setActionLoading(`${tenantId}-suspend`)
    try {
      await suspendInstanceV1AdminInstancesNamespaceSuspendPost({
        path: { namespace: tenantId },
        headers,
      })
      onRefresh()
    } catch (err) {
      alert('Failed to suspend instance')
    } finally {
      setActionLoading(null)
    }
  }, [headers, onRefresh])

  const resumeInstance = useCallback(async (tenantId: string) => {
    setActionLoading(`${tenantId}-resume`)
    try {
      await resumeInstanceV1AdminInstancesNamespaceResumePost({
        path: { namespace: tenantId },
        headers,
      })
      onRefresh()
    } catch (err) {
      alert('Failed to resume instance')
    } finally {
      setActionLoading(null)
    }
  }, [headers, onRefresh])

  const deleteInstance = useCallback(async (tenantId: string) => {
    setActionLoading(`${tenantId}-delete`)
    try {
      await deleteInstanceV1AdminInstancesNamespaceDelete({
        path: { namespace: tenantId },
        headers,
      })
      onRefresh()
    } catch (err) {
      alert('Failed to delete instance')
    } finally {
      setActionLoading(null)
    }
  }, [headers, onRefresh])

  const handleInstanceAction = useCallback(async (tenantId: string, action: 'suspend' | 'resume' | 'delete') => {
    switch (action) {
      case 'suspend':
        await suspendInstance(tenantId)
        break
      case 'resume':
        await resumeInstance(tenantId)
        break
      case 'delete':
        await deleteInstance(tenantId)
        break
    }
  }, [suspendInstance, resumeInstance, deleteInstance])

  return {
    actionLoading,
    handleInstanceAction,
  }
}
