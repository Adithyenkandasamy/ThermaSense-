import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Factory,
  Gauge,
  Map,
  Radio,
  Server,
  XCircle,
} from "lucide-react";

import { API_BASE_URL } from "./api/client";
import { useHealth } from "./hooks/useHealth";

const navItems = [
  { label: "Overview", icon: Gauge },
  { label: "Live Monitor", icon: Radio },
  { label: "Thermal Events", icon: Activity },
  { label: "Alerts", icon: AlertTriangle },
  { label: "Analytics", icon: BarChart3 },
  { label: "Facilities", icon: Factory },
  { label: "System Status", icon: Server },
];

const demoMetrics = [
  { label: "Active Events", value: 32 },
  { label: "High Risk", value: 4 },
  { label: "Extreme Risk", value: 1 },
  { label: "Industrial", value: 12 },
  { label: "Wildfire", value: 7 },
];

const riskRows = [
  ["LOW", "18", "bg-emerald-400"],
  ["MODERATE", "9", "bg-yellow-300"],
  ["HIGH", "4", "bg-orange-500"],
  ["EXTREME", "1", "bg-red-500"],
];

export default function App() {
  const backend = useHealth();
  const StatusIcon = backend.online ? CheckCircle2 : XCircle;

  return (
    <main className="min-h-screen bg-obsidian text-slate-100">
      <div className="grid min-h-screen grid-cols-[240px_1fr]">
        <aside className="border-r border-panelLine bg-panel px-4 py-5">
          <div className="mb-8">
            <div className="text-xl font-semibold tracking-wide">THERMASENSE</div>
            <div className="mt-1 text-xs uppercase text-thermal">DEMO MODE</div>
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  className="flex h-10 w-full items-center gap-3 rounded-md px-3 text-left text-sm text-slate-300 hover:bg-slate-800 hover:text-white"
                >
                  <Icon size={17} />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="flex flex-col">
          <header className="flex h-16 items-center justify-between border-b border-panelLine px-6">
            <div>
              <h1 className="text-lg font-semibold">Operations Overview</h1>
              <p className="text-xs text-slate-400">
                {backend.online
                  ? "Backend connected. Live API wiring is ready."
                  : "Frontend is running. Backend API is not connected yet."}
              </p>
            </div>
            <div
              className={`flex items-center gap-2 rounded-md border px-3 py-1 text-xs ${
                backend.online
                  ? "border-emerald-400/40 text-emerald-200"
                  : "border-red-400/40 text-red-200"
              }`}
            >
              <StatusIcon size={15} />
              API: {backend.loading ? "checking" : backend.online ? "online" : "offline"}
            </div>
          </header>

          {!backend.online && (
            <div className="border-b border-red-500/30 bg-red-950/30 px-6 py-3 text-sm text-red-100">
              Backend is not running at <span className="font-mono">{API_BASE_URL}</span>. Start it
              with <span className="font-mono">docker-compose --env-file .env.example up --build</span>.
            </div>
          )}

          <div className="grid flex-1 grid-cols-[1fr_360px] gap-4 p-4">
            <section className="flex flex-col gap-4">
              <div className="grid grid-cols-5 gap-3">
                {demoMetrics.map((metric) => (
                  <div key={metric.label} className="rounded-md border border-panelLine bg-panel p-4">
                    <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
                      <span>{metric.label}</span>
                      <span className="rounded border border-thermal/40 px-1.5 py-0.5 text-[10px] uppercase text-thermal">
                        demo
                      </span>
                    </div>
                    <div className="mt-2 text-2xl font-semibold">{metric.value}</div>
                  </div>
                ))}
              </div>

              <div className="relative min-h-[520px] rounded-md border border-panelLine bg-[#0b1118]">
                <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(#233044_1px,transparent_1px),linear-gradient(90deg,#233044_1px,transparent_1px)] [background-size:42px_42px]" />
                <div className="absolute left-[48%] top-[38%] h-12 w-12 rounded-full border-4 border-orange-500 bg-orange-500/20" />
                <div className="absolute left-[57%] top-[46%] h-8 w-8 rounded-full border-4 border-red-500 bg-red-500/20" />
                <div className="absolute left-[34%] top-[56%] h-7 w-7 rounded-full border-4 border-yellow-300 bg-yellow-300/20" />
                <div className="absolute bottom-4 left-4 flex items-center gap-3 rounded-md border border-panelLine bg-panel/90 px-3 py-2 text-xs">
                  <Map size={16} />
                  Demo GIS layer. Live map data needs backend APIs.
                </div>
              </div>
            </section>

            <aside className="space-y-4">
              <div className="rounded-md border border-panelLine bg-panel p-4">
                <h2 className="text-sm font-semibold">Priority Events</h2>
                <div className="mt-3 space-y-3">
                  {["Likely industrial thermal source", "Abnormally high anomaly", "Potential wildfire"].map(
                    (title) => (
                      <div key={title} className="rounded-md border border-panelLine bg-slate-950/40 p-3">
                        <div className="text-sm font-medium">{title}</div>
                        <div className="mt-1 text-xs text-slate-400">
                          Demo placeholder. Real investigation data will come from backend APIs.
                        </div>
                      </div>
                    ),
                  )}
                </div>
              </div>

              <div className="rounded-md border border-panelLine bg-panel p-4">
                <h2 className="text-sm font-semibold">System Status</h2>
                <div className="mt-3 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">API</span>
                    <span className={backend.online ? "text-emerald-300" : "text-red-300"}>
                      {backend.loading ? "CHECKING" : backend.online ? "ONLINE" : "OFFLINE"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">DATABASE</span>
                    <span
                      className={
                        backend.health?.checks.database === "ok" ? "text-emerald-300" : "text-slate-500"
                      }
                    >
                      {backend.health?.checks.database?.toUpperCase() ?? "UNKNOWN"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">POSTGIS</span>
                    <span className="text-slate-300">{backend.health?.checks.postgis_version ?? "UNKNOWN"}</span>
                  </div>
                </div>
              </div>

              <div className="rounded-md border border-panelLine bg-panel p-4">
                <h2 className="text-sm font-semibold">Risk Distribution</h2>
                <div className="mt-3 space-y-3">
                  {riskRows.map(([label, value, color]) => (
                    <div key={label} className="grid grid-cols-[82px_1fr_32px] items-center gap-3 text-xs">
                      <span className="text-slate-400">{label}</span>
                      <span className="h-2 rounded bg-slate-800">
                        <span className={`block h-2 rounded ${color}`} style={{ width: `${Number(value) * 5}%` }} />
                      </span>
                      <span className="text-right">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </aside>
          </div>
        </section>
      </div>
    </main>
  );
}
