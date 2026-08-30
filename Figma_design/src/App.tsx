import React, { useState } from 'react';
import { 
  Flame, Leaf, Factory, Settings, Bell, Search, 
  Map as MapIcon, Crosshair, Thermometer, Wind, Droplets,
  Activity, Navigation, CheckCircle2, CloudFog
} from 'lucide-react';

export default function App() {
  const [activeSource, setActiveSource] = useState('NOAA-20');

  return (
    <div className="relative size-full overflow-hidden flex flex-col font-sans bg-[#0a0d14] text-gray-200">
      {/* Background Map Simulation */}
      <div className="absolute inset-0 z-0">
        <img 
          src="https://images.unsplash.com/photo-1524661135-423995f22d0b?auto=format&fit=crop&w=2400&q=80" 
          alt="Satellite view" 
          className="w-full h-full object-cover opacity-30 grayscale contrast-125"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0a0d14] via-transparent to-[#0a0d14]/80"></div>
        
        {/* Mock Hotspot Marker */}
        <div className="absolute top-[45%] left-[55%] -translate-x-1/2 -translate-y-1/2">
          <div className="relative">
            <div className="absolute inset-0 bg-orange-500 rounded-full animate-ping opacity-50"></div>
            <div className="relative w-4 h-4 bg-orange-500 rounded-full border-2 border-white shadow-[0_0_15px_rgba(255,85,0,0.8)]"></div>
          </div>
        </div>
      </div>

      {/* Top Bar */}
      <header className="relative z-10 glass-panel border-x-0 border-t-0 border-b flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(0,210,255,0.4)]">
            <Thermometer className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-semibold tracking-wide text-white">ThermaSense</span>
        </div>
        
        <div className="flex-1 max-w-lg px-8">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input 
              type="text" 
              placeholder="Search coordinates, region or event ID..." 
              className="w-full bg-white/5 border border-white/10 rounded-full py-1.5 pl-10 pr-4 text-sm focus:outline-none focus:border-cyan-500/50 transition-colors"
            />
          </div>
        </div>

        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2 px-3 py-1 bg-green-500/10 rounded-full border border-green-500/20">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            <span className="text-xs font-medium text-green-400 uppercase tracking-wider">Live Data</span>
          </div>
          <div className="flex items-center gap-4 text-gray-400">
            <Bell className="w-5 h-5 hover:text-white transition-colors cursor-pointer" />
            <Settings className="w-5 h-5 hover:text-white transition-colors cursor-pointer" />
            <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-600 overflow-hidden ml-2 cursor-pointer">
              <img src="https://images.unsplash.com/photo-1568602471122-7832951cc4c5?auto=format&fit=crop&w=100&q=80" alt="User" />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="relative z-10 flex-1 flex overflow-hidden">
        
        {/* Left Sidebar */}
        <aside className="w-72 glass-panel border-y-0 border-l-0 m-4 rounded-xl flex flex-col h-[calc(100%-2rem)]">
          <div className="p-5 flex-1 overflow-y-auto space-y-6">
            
            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Satellite Source</h3>
              <div className="flex p-1 bg-black/40 rounded-lg">
                {['NOAA-20', 'NOAA-21'].map(src => (
                  <button 
                    key={src}
                    onClick={() => setActiveSource(src)}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all ${activeSource === src ? 'bg-white/10 text-cyan-400 shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                  >
                    {src}
                  </button>
                ))}
              </div>
            </section>

            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Analysis Parameters</h3>
              <div className="space-y-3">
                <div className="space-y-1">
                  <label className="text-xs text-gray-500">Date Range (UTC)</label>
                  <select className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500/50">
                    <option>Last 24 Hours</option>
                    <option>Last 3 Days</option>
                    <option>Last 5 Days</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-gray-500">Confidence Threshold</label>
                  <div className="flex items-center gap-3">
                    <input type="range" className="flex-1 accent-cyan-500" defaultValue="80" />
                    <span className="text-xs font-mono text-cyan-400">80%</span>
                  </div>
                </div>
              </div>
            </section>

            <button className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-semibold py-2.5 rounded-lg text-sm shadow-[0_0_15px_rgba(0,210,255,0.3)] transition-all">
              FETCH THERMAL DATA
            </button>

            <section className="pt-4 border-t border-white/10">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Event Legend</h3>
              <div className="space-y-2.5">
                {[
                  { icon: Flame, color: 'text-orange-500', label: 'Wildfire' },
                  { icon: Leaf, color: 'text-amber-500', label: 'Vegetation Fire' },
                  { icon: CloudFog, color: 'text-yellow-500', label: 'Agri Burning' },
                  { icon: Factory, color: 'text-purple-400', label: 'Industrial Heat' },
                  { icon: Activity, color: 'text-red-500', label: 'Volcanic' },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm text-gray-300">
                    <item.icon className={`w-4 h-4 ${item.color}`} />
                    <span>{item.label}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
          
          <div className="p-4 border-t border-white/10">
            <button className="w-full py-2 text-xs font-medium text-gray-400 hover:text-white border border-white/10 rounded-lg hover:bg-white/5 transition-colors">
              Data Archive Access
            </button>
          </div>
        </aside>

        {/* Center Workspace */}
        <main className="flex-1 flex flex-col p-4 relative">
          
          {/* Top Analytics Row */}
          <div className="grid grid-cols-4 gap-4 mb-4">
            {[
              { label: 'TOTAL HOTSPOTS', value: '1,428', change: '+12%', icon: Crosshair },
              { label: 'AGRI BURNING', value: '843', change: '+6%', icon: Leaf },
              { label: 'INDUSTRIAL HEAT', value: '312', change: '-2%', icon: Factory },
              { label: 'HIGH CONFIDENCE', value: '94%', change: '', icon: CheckCircle2 },
            ].map((stat, i) => (
              <div key={i} className="glass-panel p-4 rounded-xl flex flex-col gap-1">
                <div className="flex items-center justify-between text-gray-400 mb-1">
                  <span className="text-[10px] font-semibold uppercase tracking-wider">{stat.label}</span>
                  <stat.icon className="w-4 h-4 opacity-50" />
                </div>
                <div className="flex items-end gap-3">
                  <span className="text-2xl font-light text-white tracking-tight">{stat.value}</span>
                  {stat.change && (
                    <span className={`text-xs font-medium mb-1 ${stat.change.startsWith('+') ? 'text-orange-400' : 'text-green-400'}`}>
                      {stat.change}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex-1"></div>

          {/* Bottom Event Timeline */}
          <div className="glass-panel rounded-xl p-4 mb-2">
            <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Recent Thermal Events</h3>
            <div className="flex gap-4">
              {[
                { time: '10:45 UTC', loc: 'Northern California', type: 'Wildfire', status: 'High conf.' },
                { time: '13:45 UTC', loc: 'Industrial Port', type: 'Industrial Heat', status: 'Verified' },
                { time: '17:10 UTC', loc: 'Central Valley', type: 'Agri Burning', status: 'Medium conf.' },
              ].map((ev, i) => (
                <div key={i} className="flex-1 bg-black/20 border border-white/5 rounded-lg p-3 hover:bg-white/5 cursor-pointer transition-colors">
                  <div className="text-[10px] text-cyan-400 font-mono mb-1">{ev.time}</div>
                  <div className="text-sm font-medium text-white">{ev.type}</div>
                  <div className="text-xs text-gray-400">{ev.loc}</div>
                  <div className="text-[10px] text-gray-500 mt-2 uppercase tracking-wide">{ev.status}</div>
                </div>
              ))}
            </div>
          </div>
        </main>

        {/* Right Floating Analysis Panel */}
        <aside className="w-80 glass-panel m-4 rounded-xl flex flex-col h-[calc(100%-2rem)]">
          <div className="p-5 border-b border-white/10 bg-gradient-to-b from-white/[0.02] to-transparent">
            <h2 className="text-xs font-bold text-gray-200 uppercase tracking-widest mb-4">Hotspot Intelligence</h2>
            
            <div className="space-y-1 mb-4">
              <div className="text-lg font-medium text-white">Northern California</div>
              <div className="text-xs font-mono text-cyan-400">37.95°N, 121.5°W</div>
            </div>

            <div className="p-3 bg-orange-500/10 border border-orange-500/20 rounded-lg">
              <div className="text-[10px] text-orange-400/80 uppercase font-semibold tracking-wider mb-1">Likely Cause</div>
              <div className="text-orange-400 font-medium flex items-center gap-2">
                <Flame className="w-4 h-4" /> Wildfire (Expanding)
              </div>
            </div>
          </div>

          <div className="p-5 flex-1 overflow-y-auto space-y-6">
            
            <section>
              <div className="flex justify-between items-end mb-2">
                <span className="text-xs text-gray-400 font-medium">Confidence</span>
                <span className="text-sm font-mono text-white">94%</span>
              </div>
              <div className="h-1.5 w-full bg-black/50 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-400 w-[94%] shadow-[0_0_10px_rgba(0,210,255,0.5)]"></div>
              </div>
            </section>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-black/20 rounded-lg p-3 border border-white/5">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Heat Intensity</div>
                <div className="text-lg font-medium text-white">342.5<span className="text-xs text-gray-400 ml-1">K</span></div>
              </div>
              <div className="bg-black/20 rounded-lg p-3 border border-white/5">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Persistence</div>
                <div className="text-lg font-medium text-white">2.4<span className="text-xs text-gray-400 ml-1">hrs</span></div>
              </div>
            </div>

            <section>
              <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Supporting Evidence</h3>
              <div className="space-y-2">
                {[
                  'Located near forest/vegetation',
                  'Low humidity conditions',
                  'Thermal activity expanding',
                  'No industrial source nearby'
                ].map((evidence, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-gray-300">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                    <span className="leading-tight">{evidence}</span>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Environmental Context</h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="flex items-center gap-2 text-xs text-gray-300 bg-white/5 p-2 rounded-md">
                  <Thermometer className="w-3.5 h-3.5 text-gray-400" /> 32°C
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-300 bg-white/5 p-2 rounded-md">
                  <Droplets className="w-3.5 h-3.5 text-gray-400" /> 18%
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-300 bg-white/5 p-2 rounded-md">
                  <Wind className="w-3.5 h-3.5 text-gray-400" /> 15 km/h
                </div>
              </div>
            </section>

          </div>
        </aside>
      </div>
    </div>
  );
}