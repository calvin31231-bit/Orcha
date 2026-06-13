import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  ChevronDown,
  Clock,
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
  X,
} from 'lucide-react'

interface ServerStatus {
  last_fetch: string
  next_fetch: string
  items_tracked: number
}

interface Opportunity {
  type_id: number
  type_name: string
  buy_price: number
  sell_price: number
  net_margin_pct: number
  edcy: number
  volume: number
}

type OrderState = 'HOLD' | 'OUTBID' | 'EVACUATE' | 'BUYOUT'

interface RadarOrder {
  order_id: number
  type_name: string
  state: OrderState
  wall_thickness: number
  recommended_price: number
  current_price: number
}

interface TrackFormData {
  type_id: string
  type_name: string
  region_id: string
}

interface DashboardProps {
  status: ServerStatus | null
  activeView?: string
}

function formatISK(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toLocaleString()
}

function marginColor(pct: number): string {
  if (pct >= 15) return 'text-emerald-400'
  if (pct >= 5) return 'text-yellow-400'
  return 'text-red-400'
}

function marginBg(pct: number): string {
  if (pct >= 15) return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
  if (pct >= 5) return 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20'
  return 'bg-red-500/10 text-red-300 border-red-500/20'
}

const ORDER_STATE_CONFIG: Record<OrderState, { label: string; classes: string; icon: React.ReactNode }> = {
  HOLD: { label: 'HOLD', classes: 'bg-blue-500/15 text-blue-300 border-blue-500/30', icon: <Clock size={11} /> },
  OUTBID: { label: 'OUTBID', classes: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30', icon: <ChevronDown size={11} /> },
  EVACUATE: { label: 'EVACUATE', classes: 'bg-red-500/15 text-red-300 border-red-500/30', icon: <ShieldAlert size={11} /> },
  BUYOUT: { label: 'BUYOUT', classes: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', icon: <TrendingUp size={11} /> },
}

function StatusBar({ status }: { status: ServerStatus | null }) {
  const connected = status !== null
  return (
    <div className="flex items-center gap-4 px-6 py-2.5 bg-[#0d1120] border-b border-gray-800 text-xs text-gray-400 flex-shrink-0">
      <span className={['flex items-center gap-1.5 px-2.5 py-1 rounded-full border font-medium', connected ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400' : 'bg-red-500/10 border-red-500/25 text-red-400'].join(' ')}>
        <span className={['w-1.5 h-1.5 rounded-full', connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'].join(' ')} />
        {connected ? 'Connected' : 'Disconnected'}
      </span>
      <span className="text-gray-600">|</span>
      <span className="flex items-center gap-1.5">
        <Clock size={11} className="text-gray-600" />
        Last Sync: <span className="text-gray-200 font-medium">{status?.last_fetch ?? '—'}</span>
      </span>
      <span className="flex items-center gap-1.5">
        <RefreshCw size={11} className="text-gray-600" />
        Next Sync: <span className="text-gray-200 font-medium">{status?.next_fetch ?? '—'}</span>
      </span>
      <span className="ml-auto flex items-center gap-1.5">
        Items Tracked: <span className="text-cyan-300 font-bold tabular-nums">{status?.items_tracked ?? '—'}</span>
      </span>
    </div>
  )
}

function OpportunitiesTable() {
  const [rows, setRows] = useState<Opportunity[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('http://localhost:5000/api/opportunities')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setRows(await res.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="flex flex-col bg-gray-900 rounded-xl border border-gray-700 overflow-hidden h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-2">
          <TrendingUp size={15} className="text-cyan-400" />
          <h2 className="text-sm font-semibold text-gray-100 tracking-wide uppercase">Opportunities</h2>
          {rows.length > 0 && <span className="text-[10px] bg-gray-800 border border-gray-700 text-gray-400 px-1.5 py-0.5 rounded-full">{rows.length}</span>}
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs transition-colors disabled:opacity-50">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />Refresh
        </button>
      </div>
      <div className="overflow-y-auto flex-1">
        {error ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-red-400 text-sm">
            <AlertTriangle size={20} /><span>{error}</span>
            <button onClick={load} className="text-xs text-gray-400 underline hover:text-gray-200">Retry</button>
          </div>
        ) : rows.length === 0 && !loading ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-gray-600 text-sm">
            <TrendingUp size={28} /><span>No opportunities found</span>
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-gray-900 z-10">
              <tr className="border-b border-gray-700">
                {[{label:'Item Name',cls:'text-left pl-4'},{label:'Buy Price',cls:'text-right'},{label:'Sell Price',cls:'text-right'},{label:'Margin %',cls:'text-right'},{label:'EDCY (ISK/day)',cls:'text-right'},{label:'Volume',cls:'text-right pr-4'}].map(col => (
                  <th key={col.label} className={`py-2.5 font-semibold text-gray-500 uppercase tracking-wider ${col.cls}`}>{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.type_id} className={['border-b border-gray-800 hover:bg-gray-800/50 transition-colors', i % 2 === 0 ? '' : 'bg-gray-900/40'].join(' ')}>
                  <td className="pl-4 py-2.5 text-gray-200 font-medium max-w-[160px] truncate">{row.type_name}</td>
                  <td className="py-2.5 text-right text-gray-300 tabular-nums">{formatISK(row.buy_price)}</td>
                  <td className="py-2.5 text-right text-gray-300 tabular-nums">{formatISK(row.sell_price)}</td>
                  <td className="py-2.5 text-right">
                    <span className={['inline-block px-2 py-0.5 rounded-full border text-[10px] font-bold tabular-nums', marginBg(row.net_margin_pct)].join(' ')}>
                      {row.net_margin_pct.toFixed(1)}%
                    </span>
                  </td>
                  <td className={`py-2.5 text-right font-semibold tabular-nums ${marginColor(row.net_margin_pct)}`}>{formatISK(row.edcy)}</td>
                  <td className="pr-4 py-2.5 text-right text-gray-400 tabular-nums">{row.volume?.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {loading && rows.length === 0 && <div className="flex items-center justify-center h-full"><Loader2 size={24} className="animate-spin text-cyan-500 opacity-60" /></div>}
      </div>
    </div>
  )
}

function RadarPanel() {
  const [orders, setOrders] = useState<RadarOrder[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('http://localhost:5000/api/orders/radar')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setOrders(await res.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="flex flex-col bg-gray-900 rounded-xl border border-gray-700 overflow-hidden h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-2">
          <ShieldAlert size={15} className="text-amber-400" />
          <h2 className="text-sm font-semibold text-gray-100 tracking-wide uppercase">Order Radar</h2>
          {orders.length > 0 && <span className="text-[10px] bg-gray-800 border border-gray-700 text-gray-400 px-1.5 py-0.5 rounded-full">{orders.length}</span>}
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs transition-colors disabled:opacity-50">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />Refresh
        </button>
      </div>
      <div className="overflow-y-auto flex-1 p-3 flex flex-col gap-2">
        {error ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-red-400 text-sm">
            <AlertTriangle size={20} /><span>{error}</span>
            <button onClick={load} className="text-xs text-gray-400 underline hover:text-gray-200">Retry</button>
          </div>
        ) : loading && orders.length === 0 ? (
          <div className="flex items-center justify-center h-full"><Loader2 size={24} className="animate-spin text-amber-500 opacity-60" /></div>
        ) : orders.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-gray-600 text-sm"><ShieldAlert size={28} /><span>No active orders</span></div>
        ) : (
          orders.map((order) => {
            const cfg = ORDER_STATE_CONFIG[order.state] ?? ORDER_STATE_CONFIG.HOLD
            return (
              <div key={order.order_id} className="bg-gray-800 border border-gray-700 rounded-lg p-3 hover:border-gray-600 transition-colors">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-gray-100 text-xs font-semibold leading-tight flex-1 truncate">{order.type_name}</span>
                  <span className={['flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-bold tracking-wider flex-shrink-0', cfg.classes].join(' ')}>
                    {cfg.icon}{cfg.label}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
                  <div className="flex justify-between"><span className="text-gray-500">Current</span><span className="text-gray-300 tabular-nums font-medium">{formatISK(order.current_price)}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Suggested</span><span className="text-cyan-300 tabular-nums font-bold">{formatISK(order.recommended_price)}</span></div>
                  <div className="flex justify-between col-span-2"><span className="text-gray-500">Wall Thickness</span><span className="text-gray-300 tabular-nums">{order.wall_thickness.toLocaleString()} units</span></div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

function AIBriefCard() {
  const [brief, setBrief] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generate = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('http://localhost:5000/api/brief')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setBrief(typeof data === 'string' ? data : data.brief ?? JSON.stringify(data, null, 2))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden flex-shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Brain size={15} className="text-violet-400" />
          <h2 className="text-sm font-semibold text-gray-100 tracking-wide uppercase">AI Market Brief</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-[10px] text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded-full">
            <Brain size={9} />Powered by Mordu AI (DeepSeek-R2)
          </span>
          <button onClick={generate} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-violet-700 hover:bg-violet-600 text-white text-xs font-medium transition-colors disabled:opacity-50">
            {loading ? <><Loader2 size={12} className="animate-spin" />Generating…</> : <><Brain size={12} />Generate Smart Brief</>}
          </button>
        </div>
      </div>
      <div className="px-4 py-3 min-h-[80px] max-h-[200px] overflow-y-auto">
        {loading && (
          <div className="flex gap-1.5 items-center">
            {[0,1,2,3,4].map(i => <span key={i} className="w-1.5 h-1.5 rounded-full bg-violet-500" style={{animation:`pulse-dot 1.2s ease-in-out ${i*0.15}s infinite`}} />)}
            <span className="ml-2 text-xs text-gray-500 italic">Analysing market conditions…</span>
            <style>{`@keyframes pulse-dot{0%,80%,100%{opacity:.2;transform:scale(.8)}40%{opacity:1;transform:scale(1)}}`}</style>
          </div>
        )}
        {error && <div className="flex items-center gap-2 text-red-400 text-xs"><AlertTriangle size={13} />{error}</div>}
        {brief && !loading && <div className="text-gray-300 text-xs leading-relaxed whitespace-pre-wrap font-mono" style={{fontFamily:"'JetBrains Mono','Fira Code',monospace"}}>{brief}</div>}
        {!brief && !loading && !error && <p className="text-gray-600 text-xs italic">Click "Generate Smart Brief" to receive an AI-powered market analysis.</p>}
      </div>
    </div>
  )
}

function AddItemModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState<TrackFormData>({ type_id: '', type_name: '', region_id: '10000002' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  const handleOverlayClick = (e: React.MouseEvent) => { if (e.target === overlayRef.current) onClose() }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.type_id || !form.type_name || !form.region_id) { setError('All fields are required.'); return }
    setLoading(true); setError(null)
    try {
      const res = await fetch('http://localhost:5000/api/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type_id: parseInt(form.type_id, 10), type_name: form.type_name.trim(), region_id: parseInt(form.region_id, 10) }),
      })
      if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`)
      setSuccess(true)
      setTimeout(() => { onSuccess(); onClose() }, 900)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div ref={overlayRef} onClick={handleOverlayClick} className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <div className="flex items-center gap-2"><Plus size={16} className="text-cyan-400" /><h3 className="text-sm font-semibold text-gray-100">Track New Item</h3></div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors"><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 flex flex-col gap-4">
          {[{key:'type_id',label:'Type ID',type:'number',placeholder:'e.g. 34'},{key:'type_name',label:'Type Name',type:'text',placeholder:'e.g. Tritanium'},{key:'region_id',label:'Region ID',type:'number',placeholder:'10000002',note:'(default: The Forge)'}].map(field => (
            <div key={field.key} className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                {field.label}{field.note && <span className="ml-1.5 text-gray-600 normal-case tracking-normal">{field.note}</span>}
              </label>
              <input type={field.type} placeholder={field.placeholder}
                value={form[field.key as keyof TrackFormData]}
                onChange={e => setForm(f => ({...f,[field.key]:e.target.value}))}
                className="bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30 transition-colors" />
            </div>
          ))}
          {error && <div className="flex items-start gap-2 text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-md p-2.5"><AlertTriangle size={13} className="mt-0.5 flex-shrink-0" />{error}</div>}
          {success && <div className="flex items-center gap-2 text-emerald-400 text-xs bg-emerald-500/10 border border-emerald-500/20 rounded-md p-2.5"><CheckCircle2 size={13} />Item added successfully!</div>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium transition-colors">Cancel</button>
            <button type="submit" disabled={loading || success} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium transition-colors disabled:opacity-50">
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
              {loading ? 'Adding…' : 'Add Item'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Dashboard({ status }: DashboardProps) {
  const [showAddModal, setShowAddModal] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <StatusBar status={status} />
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-[#0d1120] flex-shrink-0">
        <h1 className="text-sm font-semibold text-gray-300 tracking-wider uppercase">Market Intelligence</h1>
        <button onClick={() => setShowAddModal(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-cyan-700 hover:bg-cyan-600 text-white text-xs font-medium transition-colors">
          <Plus size={13} />Track Item
        </button>
      </div>
      <div className="flex-1 overflow-hidden flex flex-col p-4 gap-4 min-h-0">
        <div className="flex gap-4 flex-1 min-h-0" key={refreshKey}>
          <div className="flex-[6] min-w-0 min-h-0"><OpportunitiesTable /></div>
          <div className="flex-[4] min-w-0 min-h-0"><RadarPanel /></div>
        </div>
        <AIBriefCard />
      </div>
      {showAddModal && <AddItemModal onClose={() => setShowAddModal(false)} onSuccess={() => setRefreshKey(k => k + 1)} />}
    </div>
  )
}
