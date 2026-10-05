import { useState, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import {
  getAdminDashboardV1AdminDashboardGet,
  getSystemAlertsV1AdminAlertsGet,
  listTenantsV1AdminTenantsGet,
  listUsersV1AdminUsersGet,
  listK8sInstancesV1AdminInstancesGet,
  type UserResponse,
  type TenantResponse,
  type K8sInstanceSummary,
  type AlertItem,
  type AdminDashboard,
} from '@/lib/api'

// Type aliases for cleaner usage
type User = UserResponse
type Tenant = TenantResponse
type Instance = K8sInstanceSummary
type Alert = AlertItem

// Extended user type for recent signups that include tenant info
interface UserWithTenant extends UserResponse {
  tenant_name?: string
  tenant_id?: string
}

// Response type for list endpoints (API returns unknown, so we define proper types)
interface UsersListResponse {
  users: User[]
}

interface TenantsListResponse {
  tenants: Tenant[]
}

interface InstancesListResponse {
  instances: Instance[]
}

interface AlertsListResponse {
  alerts: Alert[]
}

export function useAdminDashboard() {
  const { data: session } = useSession()
  const [dashboardData, setDashboardData] = useState<AdminDashboard | null>(null)
  const [users, setUsers] = useState<UserWithTenant[]>([])
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [instances, setInstances] = useState<Instance[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const token = (session as any)?.accessToken

  const fetchDashboardData = useCallback(async () => {
    if (!token) return

    setLoading(true)
    setError(null)
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined

      const [dashboardRes, alertsRes, tenantsRes] = await Promise.all([
        getAdminDashboardV1AdminDashboardGet({ headers }),
        getSystemAlertsV1AdminAlertsGet({ headers }),
        listTenantsV1AdminTenantsGet({ query: { limit: 50 }, headers }),
      ])

      if (dashboardRes.data) {
        const dashboard = dashboardRes.data as AdminDashboard
        setDashboardData(dashboard)
        setUsers((dashboard.recent_signups || []).map((u) => ({
          ...u,
          tenant_name: (u as { tenant_name?: string }).tenant_name,
          tenant_id: (u as { tenant_id?: string }).tenant_id,
        })) as UserWithTenant[])
      }

      if (alertsRes.data) {
        const alertsResp = alertsRes.data as AlertsListResponse
        setAlerts(alertsResp.alerts || [])
      }

      if (tenantsRes.data) {
        const tenantsResp = tenantsRes.data as TenantsListResponse
        setTenants(tenantsResp.tenants || [])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [token])

  const fetchUsers = useCallback(async () => {
    if (!token) return
    try {
      const { data } = await listUsersV1AdminUsersGet({
        query: { limit: 50 },
        headers: { Authorization: `Bearer ${token}` },
      })
      const usersResp = data as UsersListResponse | undefined
      setUsers(usersResp?.users || [])
    } catch (err) {
      console.error('Failed to fetch users:', err)
    }
  }, [token])

  const fetchTenants = useCallback(async () => {
    if (!token) return
    try {
      const { data } = await listTenantsV1AdminTenantsGet({
        query: { limit: 50 },
        headers: { Authorization: `Bearer ${token}` },
      })
      const tenantsResp = data as TenantsListResponse | undefined
      setTenants(tenantsResp?.tenants || [])
    } catch (err) {
      console.error('Failed to fetch tenants:', err)
    }
  }, [token])

  const fetchInstances = useCallback(async () => {
    if (!token) return
    try {
      const { data } = await listK8sInstancesV1AdminInstancesGet({
        headers: { Authorization: `Bearer ${token}` },
      })
      const instancesResp = data as InstancesListResponse | undefined
      setInstances(instancesResp?.instances || [])
    } catch (err) {
      console.error('Failed to fetch instances:', err)
    }
  }, [token])

  return {
    dashboardData,
    users,
    tenants,
    instances,
    alerts,
    loading,
    error,
    fetchDashboardData,
    fetchUsers,
    fetchTenants,
    fetchInstances,
    setAlerts,
  }
}
