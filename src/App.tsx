import React, { useEffect, useState, useCallback } from 'react'
import { Command } from '@tauri-apps/api/shell'
import {
  BarChart2,
  TrendingUp,
  Radar,
  Brain,
  Settings,
  AlertTriangle,
  RefreshCw,
  Zap,
} from 'lucide-react'
import Dashboard from './components/Dashboard'

type ViewName = 'dashboard' | 'opportunities' | 'radar' | 'brief' | 'settings'

interface ServerStatus {
  last_fetch: string
  next_fetch: string
  items_tracked: number
}

interface SidecarState {
  phase: 'starting' | 'running' | 'error'
  errorMessage?: string
}

const NAV_ITEMS: { id: ViewName; label: string; icon: React.ReactNode }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <BarChart2 size={20} /> },
  { id: 'opportunities', label: 'Opportunities', icon: <TrendingUp size={20} /> },
  { id: 'radar', label: 'Order Radar', icon: <Radar size={20} /> },
  { id: 'brief', label: 'AI Brief', icon: <Brain size={20} /> },
  { id: 'settings', label: 'Settings', icon: <Settings size={20} /> },
]

const STATUS_POLL_INTERVAL = 30_000

export default function App() {
  const [sidecar, setSidecar] = useState<SidecarState>({ phase: 'starting' })
  const [activeView, setActiveView] = useState<ViewName>('dashboard')
  const [serverStatus, setServerStatus] = useState<ServerStatus | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:5000/api/status')
      if (res.ok) {
        const data: ServerStatus = await res.json()
        setServerStatus(data)
      }
    } catch {
      // status fetch is best-effort
    }
  }, [])

  const startSidecar = useCallback(async () => {
    setSidecar({ phase: 'starting' })
    try {
      const cmd = new Command('mordu_server')

      cmd.stdout.on('data', (line: string) => {
        console.log('[mordu_server stdout]', line)
        setSidecar((prev) => (prev.phase === 'starting' ? { phase: 'running' } : prev))
      })

      cmd.stderr.on('data', (line: string) => {
        console.warn('[mordu_server stderr]', line)
      })

      cmd.on('error', (err: string) => {
        console.error('[mordu_server error]', err)
        setSidecar({ phase: 'error', errorMessage: err })
      })

      cmd.on('close', (data: { code: number | null; signal: string | null }) => {
        console.warn('[mordu_server closed]', data)
        setSidecar((prev) => {
          if (prev.phase === 'running') {
            return { phase: 'error', errorMessage: `Process exited with code ${data.code ?? 'unknown'}` }
          }
          return { phase: 'error', errorMessage: `Failed to start (exit code ${data.code ?? 'unknown'})` }
        })
      })

      await cmd.spawn()

      setTimeout(() => {
        setSidecar((prev) => (prev.phase === 'starting' ? { phase: 'running' } : prev))
      }, 8_000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setSidecar({ phase: 'error', errorMessage: msg })
    }
  }, [])

  useEffect(() => {
    startSidecar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retryKey])

  useEffect(() => {
    if (sidecar.phase !== 'running') return
    fetchStatus()
    const interval = setInterval(fetchStatus, STATUS_POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [sidecar.phase, fetchStatus])

  const handleRetry = () => setRetryKey((k) => k + 1)

  if (sidecar.phase === 'starting') return <LoadingScreen />
  if (sidecar.phase === 'error') return <ErrorScreen message={sidecar.errorMessage} onRetry={handleRetry} />

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0a0e1a]">
      <aside
        style={{ width: 240 }}
        className="flex flex-col flex-shrink-0 bg-[#0d1120] border-r border-gray-800 select-none"
      >
        <div className="flex items-center gap-2 px-5 py-5 border-b border-gray-800">
          <Zap size={22} className="text-cyan-400" />
          <span className="text-lg font-bold tracking-widest text-cyan-300 uppercase">Mordu</span>
          <span className="text-[10px] text-gray-500 self-end mb-0.5 tracking-wider uppercase">Engine</span>
        </div>
        <nav className="flex flex-col gap-1 px-2 pt-4 flex-1">
          {NAV_ITEMS.map((item) => {
            const isActive = activeView === item.id
            return (
              <button
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={[
                  'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150 w-full text-left',
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60',
                ].join(' ')}
              >
                <span className={isActive ? 'text-cyan-400' : 'text-gray-500'}>{item.icon}</span>
                {item.label}
              </button>
            )
          })}
        </nav>
        <div className="px-4 py-3 border-t border-gray-800">
          <div className="flex items-center gap-2">
            <span className={['w-2 h-2 rounded-full flex-shrink-0', serverStatus ? 'bg-green-400 animate-pulse' : 'bg-yellow-400'].join(' ')} />
            <span className="text-xs text-gray-500">{serverStatus ? 'Server Connected' : 'Connecting…'}</span>
          </div>
          <p className="text-[10px] text-gray-700 mt-1">mordu_server @ :5000</p>
        </div>
      </aside>
      <main className="flex-1 overflow-hidden flex flex-col">
        {activeView === 'dashboard' || activeView === 'opportunities' || activeView === 'radar' || activeView === 'brief' ? (
          <Dashboard status={serverStatus} activeView={activeView} />
        ) : (
          <SettingsPlaceholder />
        )}
      </main>
    </div>
  )
}

function LoadingScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#0a0e1a] gap-6">
      <div className="flex items-center gap-3">
        <Zap size={32} className="text-cyan-400 animate-pulse" />
        <span className="text-3xl font-bold tracking-widest text-cyan-300 uppercase animate-pulse">Mordu Engine</span>
      </div>
      <p className="text-gray-500 text-sm tracking-wider uppercase">Initializing market intelligence core…</p>
      <div className="flex gap-1.5 mt-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i} className="w-1.5 h-1.5 rounded-full bg-cyan-500 opacity-0"
            style={{ animation: `blink 1.2s ease-in-out ${i * 0.2}s infinite` }} />
        ))}
      </div>
      <style>{`@keyframes blink { 0%, 80%, 100% { opacity: 0; } 40% { opacity: 1; } }`}</style>
    </div>
  )
}

function ErrorScreen({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#0a0e1a] gap-6">
      <div className="bg-gray-900 border border-red-500/30 rounded-xl p-8 max-w-md w-full mx-4 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <AlertTriangle size={24} className="text-red-400 flex-shrink-0" />
          <h2 className="text-lg font-bold text-red-300">Sidecar Failed to Start</h2>
        </div>
        <p className="text-gray-400 text-sm mb-2">
          The <code className="text-cyan-400 bg-gray-800 px-1 rounded">mordu_server</code> backend process could not be started.
        </p>
        {message && (
          <pre className="bg-gray-950 border border-gray-700 rounded p-3 text-xs text-red-300 overflow-x-auto whitespace-pre-wrap break-words mb-5">
            {message}
          </pre>
        )}
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-md text-sm font-medium transition-colors w-full justify-center"
        >
          <RefreshCw size={15} />
          Retry
        </button>
      </div>
    </div>
  )
}

function SettingsPlaceholder() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-gray-600 gap-3">
      <Settings size={40} />
      <p className="text-sm">Settings panel coming soon</p>
    </div>
  )
}
