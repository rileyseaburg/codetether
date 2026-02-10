'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useSession, signOut } from 'next-auth/react'
import clsx from 'clsx'

// Custom hook to get user from either NextAuth or localStorage
function useAuth() {
    const { data: session, status } = useSession()
    const [customUser, setCustomUser] = useState<any>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        // Check for custom token in localStorage
        const token = localStorage.getItem('a2a_token')
        const userStr = localStorage.getItem('a2a_user')

        if (token && userStr) {
            try {
                const user = JSON.parse(userStr)
                setCustomUser(user)
            } catch {
                // Invalid user data
                localStorage.removeItem('a2a_token')
                localStorage.removeItem('a2a_user')
            }
        }
        setIsLoading(false)
    }, [])

    // Prefer NextAuth session, fall back to custom auth
    const user = session?.user || customUser
    const isAuthenticated = status === 'authenticated' || !!customUser
    const loading = status === 'loading' || isLoading

    return { user, isAuthenticated, loading, session, customUser }
}

function FolderIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
    )
}

function ClipboardIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
    )
}

function ChatIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
    )
}

function TerminalIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
    )
}

function BoltIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
    )
}

function CogIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
    )
}

function ChartIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
    )
}

function AnalyticsIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
    )
}

function CreditCardIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
        </svg>
    )
}

function ShieldIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
    )
}

function RocketIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
        </svg>
    )
}

function LoopIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    )
}

function BrainIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.5 4a3.5 3.5 0 00-3.5 3.5v.5a3 3 0 00-2 2.83V12a3 3 0 002 2.83v.67A3.5 3.5 0 009.5 19H11v-7H9.5A1.5 1.5 0 018 10.5 1.5 1.5 0 019.5 9H11V7.5A3.5 3.5 0 009.5 4zM14.5 4A3.5 3.5 0 0118 7.5v.5a3 3 0 012 2.83V12a3 3 0 01-2 2.83v.67A3.5 3.5 0 0114.5 19H13v-7h1.5a1.5 1.5 0 001.5-1.5A1.5 1.5 0 0014.5 9H13V7.5A3.5 3.5 0 0114.5 4z" />
        </svg>
    )
}

function ServerIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
        </svg>
    )
}

function ClockIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

const navigation = [
    { name: 'Get Started', href: '/dashboard/getting-started', icon: RocketIcon, highlight: true },
    { name: 'Codebases', href: '/dashboard', icon: FolderIcon },
    { name: 'Workers', href: '/dashboard/workers', icon: ServerIcon },
    { name: 'Ralph', href: '/dashboard/ralph', icon: LoopIcon, highlight: true },
    { name: 'Cognition', href: '/dashboard/cognition', icon: BrainIcon },
    { name: 'Benchmarks', href: '/dashboard/benchmarks', icon: ChartIcon },
    { name: 'Analytics', href: '/dashboard/analytics', icon: AnalyticsIcon, highlight: true },
    { name: 'Cronjobs', href: '/cronjobs', icon: ClockIcon },
    { name: 'Tasks', href: '/dashboard/tasks', icon: ClipboardIcon },
    { name: 'Sessions', href: '/dashboard/sessions', icon: ChatIcon },
    { name: 'Output', href: '/dashboard/output', icon: TerminalIcon },
    { name: 'Activity', href: '/dashboard/activity', icon: BoltIcon },
    { name: 'Automations', href: '/dashboard/automations', icon: CogIcon },
    { name: 'Billing', href: '/dashboard/billing', icon: CreditCardIcon },
    { name: 'Settings', href: '/dashboard/settings', icon: CogIcon },
]

// Admin navigation item (shown only for admins)
const adminNavItem = { name: 'Admin', href: '/dashboard/admin', icon: ShieldIcon }

function MenuIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
    )
}

function XIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
    )
}

function SunIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="currentColor" viewBox="0 0 20 20" {...props}>
            <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" />
        </svg>
    )
}

function MoonIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="currentColor" viewBox="0 0 20 20" {...props}>
            <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
    )
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const [sidebarOpen, setSidebarOpen] = useState(false)
    const [darkMode, setDarkMode] = useState(false)
    const [userMenuOpen, setUserMenuOpen] = useState(false)
    const pathname = usePathname()
    const router = useRouter()
    const { user, isAuthenticated, loading, session, customUser } = useAuth()

    // Redirect to login if not authenticated
    useEffect(() => {
        if (!loading && !isAuthenticated) {
            router.push('/login?callbackUrl=' + encodeURIComponent(pathname))
        }
    }, [loading, isAuthenticated, router, pathname])

    // Check if user has admin role
    const isAdmin = (user as any)?.roles?.includes('admin') ||
        (user as any)?.roles?.includes('a2a-admin') ||
        (user as any)?.role === 'admin'

    // Build navigation with admin item if user is admin
    const navItems = isAdmin ? [...navigation, adminNavItem] : navigation

    useEffect(() => {
        setDarkMode(true)
        document.documentElement.classList.add('dark')
    }, [])

    const toggleDarkMode = () => {
        setDarkMode(!darkMode)
        document.documentElement.classList.toggle('dark')
    }

    const handleSignOut = () => {
        // Clear custom auth tokens from localStorage
        localStorage.removeItem('a2a_token')
        localStorage.removeItem('a2a_user')
        localStorage.removeItem('a2a_refresh_token')
        localStorage.removeItem('a2a_session')
        localStorage.removeItem('access_token')

        // Clear cookie
        document.cookie = 'a2a_token=; path=/; max-age=0'

        // Sign out from NextAuth if using that
        if (session) {
            signOut({ callbackUrl: '/' })
        } else {
            router.push('/')
        }
    }

    // Show loading state
    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center bg-gray-900">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
            </div>
        )
    }

    // Don't render if not authenticated (will redirect)
    if (!isAuthenticated) {
        return null
    }

    return (
        <div className={clsx('h-screen overflow-hidden relative', darkMode && 'dark')}>
            {/* Mobile sidebar backdrop */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-50 bg-gray-900/80 lg:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Mobile sidebar */}
            <div className={clsx(
                'fixed inset-y-0 left-0 z-50 w-64 sm:w-72 bg-indigo-700 dark:bg-gray-800 lg:hidden transform transition-transform duration-300',
                sidebarOpen ? 'translate-x-0' : '-translate-x-full'
            )}>
                <div className="flex h-16 items-center justify-between px-6 border-b border-indigo-600 dark:border-gray-700">
                    <Link href="/dashboard" className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
                            <TerminalIcon className="h-5 w-5 text-white" />
                        </div>
                        <span className="text-lg font-semibold text-white">CodeTether</span>
                    </Link>
                    <button onClick={() => setSidebarOpen(false)} className="text-cyan-200 hover:text-white">
                        <XIcon className="h-6 w-6" />
                    </button>
                </div>
                <nav className="flex flex-col p-4">
                    <ul className="space-y-1">
                        {navItems.map((item) => (
                            <li key={item.name}>
                                <Link
                                    href={item.href}
                                    onClick={() => setSidebarOpen(false)}
                                    className={clsx(
                                        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium',
                                        pathname === item.href
                                            ? 'bg-white/10 text-white'
                                            : 'text-cyan-100 hover:bg-white/10',
                                        item.name === 'Admin' && 'border-t border-cyan-600 dark:border-gray-700 mt-2 pt-2',
                                        (item as any).highlight && 'bg-orange-500/20 text-orange-200 hover:bg-orange-500/30'
                                    )}
                                >
                                    <item.icon className={clsx('h-5 w-5', (item as any).highlight && 'text-orange-400')} />
                                    {item.name}
                                    {(item as any).highlight && (
                                        <span className="ml-auto text-[10px] bg-orange-500 text-white px-1.5 py-0.5 rounded-full">New</span>
                                    )}
                                </Link>
                            </li>
                        ))}
                    </ul>
                </nav>
            </div>

            {/* Desktop sidebar */}
            <div className="hidden md:fixed md:inset-y-0 md:z-50 md:flex md:w-60 lg:w-56 lg:flex-col">
                <div className="flex grow flex-col overflow-y-auto bg-cyan-700 dark:bg-gray-800">
                    <div className="flex h-16 items-center px-4 border-b border-cyan-600 dark:border-gray-700">
                        <Link href="/dashboard" className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
                                <TerminalIcon className="h-5 w-5 text-white" />
                            </div>
                            <span className="text-lg font-semibold text-white">CodeTether</span>
                        </Link>
                    </div>
                    <nav className="flex flex-1 flex-col p-3">
                        <ul className="space-y-1">
                            {navItems.map((item) => (
                                <li key={item.name}>
                                    <Link
                                        href={item.href}
                                        className={clsx(
                                            'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium',
                                            pathname === item.href
                                                ? 'bg-white/10 text-white'
                                                : 'text-cyan-100 hover:bg-white/10',
                                            item.name === 'Admin' && 'border-t border-cyan-600 dark:border-gray-700 mt-2 pt-2',
                                            (item as any).highlight && 'bg-orange-500/20 text-orange-200 hover:bg-orange-500/30'
                                        )}
                                    >
                                        <item.icon className={clsx('h-5 w-5', (item as any).highlight && 'text-orange-400')} />
                                        {item.name}
                                        {(item as any).highlight && (
                                            <span className="ml-auto text-[10px] bg-orange-500 text-white px-1.5 py-0.5 rounded-full">New</span>
                                        )}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                        {/* Stats in sidebar */}
                        <div className="mt-auto pt-4 border-t border-cyan-600 dark:border-gray-700">
                            <div className="grid grid-cols-2 gap-2 text-center">
                                <div className="rounded-lg bg-white/5 p-2">
                                    <div className="text-lg font-bold text-white">0</div>
                                    <div className="text-xs text-cyan-200">Codebases</div>
                                </div>
                                <div className="rounded-lg bg-white/5 p-2">
                                    <div className="text-lg font-bold text-white">0</div>
                                    <div className="text-xs text-cyan-200">Tasks</div>
                                </div>
                            </div>
                        </div>
                    </nav>
                </div>
            </div>

            {/* Main content wrapper */}
            <div className="absolute inset-0 md:left-60 lg:left-52 flex flex-col overflow-hidden">
                {/* Top navbar */}
                <div className="shrink-0 z-40 flex h-16 items-center gap-x-2 border-b border-gray-200 bg-white px-2 shadow-sm dark:border-gray-700 dark:bg-gray-800 sm:gap-x-6 sm:px-6 lg:px-8">
                    {/* Mobile menu button */}
                    <button
                        onClick={() => setSidebarOpen(true)}
                        className="md:hidden -m-2.5 p-2.5 text-gray-700 dark:text-gray-200"
                    >
                        <MenuIcon className="h-6 w-6" />
                    </button>

                    {/* Separator */}
                    <div className="h-6 w-px bg-gray-200 dark:bg-gray-700 md:hidden" />

                    <div className="flex flex-1 gap-x-2 self-stretch overflow-hidden sm:gap-x-6">
                        {/* Status indicators */}
                        <div className="hidden md:flex items-center gap-4 ml-auto">
                            <div className="flex items-center gap-2">
                                <span className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse" />
                                <span className="text-sm text-gray-600 dark:text-gray-300">Connected</span>
                            </div>
                        </div>

                        {/* Right actions */}
                        <div className="flex items-center gap-x-2 ml-auto md:ml-0 sm:gap-x-3">
                            <button
                                onClick={toggleDarkMode}
                                className="rounded-full p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white"
                            >
                                {darkMode ? <SunIcon className="h-5 w-5" /> : <MoonIcon className="h-5 w-5" />}
                            </button>
                            <button className="hidden sm:block rounded-full p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white">
                                <CogIcon className="h-5 w-5" />
                            </button>

                            {/* User menu */}
                            {user ? (
                                <div className="relative">
                                    <button
                                        onClick={() => setUserMenuOpen(!userMenuOpen)}
                                        className="flex items-center gap-1 sm:gap-2 rounded-full p-1 hover:bg-gray-100 dark:hover:bg-gray-700"
                                    >
                                        {user.image ? (
                                            <img
                                                src={user.image}
                                                alt={user.name || user.first_name || 'User'}
                                                className="h-8 w-8 rounded-full"
                                            />
                                        ) : (
                                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-600 text-white text-sm font-medium">
                                                {user.name?.charAt(0) || user.first_name?.charAt(0) || user.email?.charAt(0) || 'U'}
                                            </div>
                                        )}
                                        <span className="hidden xs:hidden sm:block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 max-w-20 sm:max-w-none truncate">
                                            {user.name || user.first_name || user.email}
                                        </span>
                                    </button>

                                    {userMenuOpen && (
                                        <>
                                            <div
                                                className="fixed inset-0 z-10"
                                                onClick={() => setUserMenuOpen(false)}
                                            />
                                            <div className="absolute right-0 sm:right-auto sm:left-0 z-20 mt-2 w-48 rounded-md bg-white dark:bg-gray-800 py-1 shadow-lg ring-1 ring-black ring-opacity-5">
                                                <div className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                                                    Signed in as
                                                    <div className="font-medium text-gray-900 dark:text-white truncate">
                                                        {user.email}
                                                    </div>
                                                </div>
                                                <Link
                                                    href="/dashboard/billing"
                                                    onClick={() => setUserMenuOpen(false)}
                                                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                                                >
                                                    Billing
                                                </Link>
                                                <Link
                                                    href="/dashboard/settings"
                                                    onClick={() => setUserMenuOpen(false)}
                                                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                                                >
                                                    Settings
                                                </Link>
                                                <button
                                                    onClick={handleSignOut}
                                                    className="block w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                                                >
                                                    Sign out
                                                </button>
                                            </div>
                                        </>
                                    )}
                                </div>
                            ) : (
                                <Link
                                    href="/login"
                                    className="text-sm font-medium text-cyan-600 hover:text-cyan-500 dark:text-cyan-400"
                                >
                                    Sign in
                                </Link>
                            )}

                            <Link
                                href="/"
                                className="hidden sm:inline-flex text-sm font-medium text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
                            >
                                ← Back to Site
                            </Link>
                        </div>
                    </div>
                </div>

                {/* Main content */}
                <main className="flex-1 min-h-0 overflow-auto px-3 sm:px-4 md:px-6 lg:px-8 py-4">
                    {children}
                </main>
            </div>
        </div>
    )
}
