import React, { useState, useEffect } from 'react';

export const Dashboard: React.FC = () => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  const formattedDate = currentTime.toLocaleDateString('vi-VN', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className="bg-transparent h-full flex flex-col space-y-6 overflow-hidden">
      
      {/* 1. HERO HEADER: Greeting & Context (LIGHT MODE) */}
      <div className="p-6 md:p-8 bg-white rounded-3xl border border-neutral-200/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] shrink-0 relative overflow-hidden group">
        {/* Decorative Blobs */}
        <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary-50 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute top-10 right-40 w-32 h-32 bg-green-50 rounded-full blur-2xl pointer-events-none"></div>
        
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-6 relative z-10">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-green-50 text-green-700 rounded-full text-[10px] font-bold uppercase tracking-widest mb-4 border border-green-100">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse"></span>
              Live System Status: Optimal
            </div>
            <h1 className="text-3xl lg:text-4xl font-black text-neutral-900 tracking-tight mb-2 flex flex-wrap items-center gap-3">
              Chào buổi sáng, Nguyễn Minh 👋
              <span className="text-xs bg-warning text-white px-2 py-1 rounded-md align-middle font-bold tracking-normal uppercase">Đang phát triển</span>
            </h1>
            <p className="text-neutral-500 font-medium text-sm flex items-center gap-2 mt-2">
              <i className="ph-fill ph-calendar-blank"></i> {formattedDate}
            </p>
          </div>
          <div className="flex flex-wrap gap-3 w-full lg:w-auto opacity-70">
            <button className="flex-1 lg:flex-none px-5 py-2.5 bg-white text-neutral-700 font-bold text-sm rounded-xl flex items-center justify-center gap-2 border border-neutral-200 shadow-sm cursor-not-allowed">
              <i className="ph-bold ph-bell"></i> Alerts (Đang phát triển) <span className="bg-danger text-white text-[10px] px-1.5 py-0.5 rounded-md ml-1">3</span>
            </button>
            <button className="flex-1 lg:flex-none px-6 py-2.5 bg-primary text-white font-bold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-primary/30 cursor-not-allowed">
              <i className="ph-bold ph-plus"></i> Quick Action (Đang phát triển)
            </button>
          </div>
        </div>
      </div>

      {/* Feature Under Development Banner */}
      <div className="bg-warning/10 border border-warning/20 rounded-xl p-4 flex items-center gap-4 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-warning/5 rounded-full blur-2xl -mr-10 -mt-10 pointer-events-none"></div>
        <div className="w-10 h-10 bg-warning/20 rounded-full flex items-center justify-center shrink-0">
          <i className="ph-fill ph-warning-circle text-warning text-xl animate-pulse"></i>
        </div>
        <div>
          <h3 className="font-bold text-neutral-900 text-sm">Tính Năng Đang Phát Triển</h3>
          <p className="text-neutral-600 text-xs mt-0.5">Bảng điều khiển tổng hợp (Dashboard) đang trong quá trình hoàn thiện. Số liệu và biểu đồ hiện tại chỉ mang tính chất minh họa giao diện.</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-6 pb-6">
        
        {/* 2. KPI GRID (Synchronized with other pages) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {[
            { label: 'Total Assets', value: '1,248', icon: 'ph-cube', color: 'text-primary', bg: 'bg-primary-50', border: 'border-primary-100', trend: '+12' },
            { label: 'Active Work Orders', value: '42', icon: 'ph-clipboard-text', color: 'text-warning', bg: 'bg-orange-50', border: 'border-orange-100', trend: '-5' },
            { label: 'Critical Alerts', value: '3', icon: 'ph-warning-circle', color: 'text-danger', bg: 'bg-red-50', border: 'border-red-100', trend: '+1' },
            { label: 'System Uptime', value: '99.9%', icon: 'ph-activity', color: 'text-success', bg: 'bg-green-50', border: 'border-green-100', trend: '+0.1%' }
          ].map((kpi, idx) => (
            <div key={idx} className="bg-white p-5 rounded-2xl border border-neutral-200 shadow-[0_2px_10px_rgba(0,0,0,0.02)] hover:shadow-md transition relative overflow-hidden group">
              <div className="flex justify-between items-start mb-4 relative z-10">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl ${kpi.bg} ${kpi.color}`}>
                  <i className={`ph-fill ${kpi.icon}`}></i>
                </div>
                <span className={`text-[10px] font-bold px-2 py-1 rounded-md uppercase tracking-wider ${kpi.trend.startsWith('+') && kpi.label !== 'Active Work Orders' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                  {kpi.trend}
                </span>
              </div>
              <div className="relative z-10">
                <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{kpi.label}</p>
                <h3 className="text-3xl font-black text-neutral-900 tracking-tight">{kpi.value}</h3>
              </div>
              <div className={`absolute -bottom-6 -right-6 w-24 h-24 rounded-full border-[12px] opacity-20 ${kpi.border} group-hover:scale-150 transition-transform duration-500 pointer-events-none`}></div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
          
          {/* 3. CLEAN CHART: Work Order Trends */}
          <div className="lg:col-span-2 bg-white rounded-3xl border border-neutral-200 shadow-[0_4px_20px_rgba(0,0,0,0.03)] overflow-hidden flex flex-col">
            <div className="p-5 border-b border-neutral-100 flex justify-between items-center bg-white/50">
              <h3 className="text-base font-bold text-neutral-900">Work Order Trends</h3>
              <div className="flex gap-2">
                <span className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600"><span className="w-2.5 h-2.5 rounded-full bg-primary"></span> Created</span>
                <span className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600"><span className="w-2.5 h-2.5 rounded-full bg-success"></span> Completed</span>
              </div>
            </div>
            <div className="p-6 flex-1 flex flex-col items-center justify-center min-h-[300px]">
              {/* Clean Fake Area Chart */}
              <svg viewBox="0 0 800 200" className="w-full h-full preserve-3d" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="chart-blue" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#00a0e2" stopOpacity="0.4"/>
                    <stop offset="100%" stopColor="#00a0e2" stopOpacity="0.05"/>
                  </linearGradient>
                  <linearGradient id="chart-green" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#52c41a" stopOpacity="0.4"/>
                    <stop offset="100%" stopColor="#52c41a" stopOpacity="0.05"/>
                  </linearGradient>
                </defs>
                {/* Grid Lines */}
                <path d="M0,50 L800,50 M0,100 L800,100 M0,150 L800,150" fill="none" stroke="#f1f5f9" strokeWidth="1" strokeDasharray="5,5" />
                <path d="M0,150 L100,120 L200,160 L300,90 L400,130 L500,70 L600,110 L700,50 L800,80" fill="none" stroke="#00a0e2" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M0,150 L100,120 L200,160 L300,90 L400,130 L500,70 L600,110 L700,50 L800,80 L800,200 L0,200 Z" fill="url(#chart-blue)" />
                <path d="M0,180 L100,160 L200,180 L300,120 L400,160 L500,100 L600,150 L700,90 L800,120" fill="none" stroke="#52c41a" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M0,180 L100,160 L200,180 L300,120 L400,160 L500,100 L600,150 L700,90 L800,120 L800,200 L0,200 Z" fill="url(#chart-green)" />
              </svg>
              <div className="w-full flex justify-between text-[10px] font-bold text-neutral-400 uppercase tracking-widest mt-4 px-2">
                <span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span>
              </div>
            </div>
          </div>

          {/* 4. ACTIVITY & QUICK STATS COLUMN */}
          <div className="space-y-6 lg:space-y-8">
            
            {/* Quick Stats: Asset Health */}
            <div className="bg-white rounded-3xl border border-neutral-200 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6">
              <h3 className="text-base font-bold text-neutral-900 mb-4">Asset Health Distribution</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-xs font-bold text-neutral-700">Healthy (Operating)</span>
                    <span className="text-xs font-black text-neutral-900">85%</span>
                  </div>
                  <div className="h-2 w-full bg-neutral-100 rounded-full overflow-hidden">
                    <div className="h-full bg-success rounded-full" style={{ width: '85%' }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-xs font-bold text-neutral-700">Warning (Maintenance Needed)</span>
                    <span className="text-xs font-black text-neutral-900">12%</span>
                  </div>
                  <div className="h-2 w-full bg-neutral-100 rounded-full overflow-hidden">
                    <div className="h-full bg-warning rounded-full" style={{ width: '12%' }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-xs font-bold text-neutral-700">Critical (Down)</span>
                    <span className="text-xs font-black text-neutral-900">3%</span>
                  </div>
                  <div className="h-2 w-full bg-neutral-100 rounded-full overflow-hidden">
                    <div className="h-full bg-danger rounded-full" style={{ width: '3%' }}></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Recent Activities */}
            <div className="bg-white rounded-3xl border border-neutral-200 shadow-[0_4px_20px_rgba(0,0,0,0.03)] overflow-hidden flex flex-col flex-1">
              <div className="px-6 py-5 border-b border-neutral-100 flex justify-between items-center bg-white/50 shrink-0">
                <h3 className="text-base font-bold text-neutral-900">Activity Feed</h3>
                <button className="text-primary text-xs font-bold hover:underline bg-primary/10 px-2 py-1 rounded-md">View All</button>
              </div>
              <div className="p-6 space-y-6 flex-1 overflow-y-auto">
                <div className="flex gap-4 group cursor-pointer">
                  <div className="w-10 h-10 rounded-2xl bg-green-50 flex items-center justify-center text-success shrink-0 mt-0.5 border border-green-100 shadow-sm group-hover:scale-110 transition-transform">
                    <i className="ph-fill ph-check-circle text-lg"></i>
                  </div>
                  <div>
                    <p className="text-sm font-black text-neutral-900 leading-tight group-hover:text-primary transition-colors">WO-0087 Completed</p>
                    <p className="text-xs text-neutral-500 mt-1.5 font-medium leading-relaxed">Preventive maintenance on CNC Machine #1 finished by Nguyen Minh.</p>
                    <p className="text-[10px] font-bold text-neutral-400 mt-2 tracking-wider">2 HOURS AGO</p>
                  </div>
                </div>
                <div className="flex gap-4 group cursor-pointer">
                  <div className="w-10 h-10 rounded-2xl bg-red-50 flex items-center justify-center text-danger shrink-0 mt-0.5 border border-red-100 shadow-sm group-hover:scale-110 transition-transform">
                    <i className="ph-fill ph-warning-circle text-lg"></i>
                  </div>
                  <div>
                    <p className="text-sm font-black text-neutral-900 leading-tight group-hover:text-primary transition-colors">Alert: Temperature High</p>
                    <p className="text-xs text-neutral-500 mt-1.5 font-medium leading-relaxed">Transformer T-01 exceeded operating temperature limit (85°C).</p>
                    <p className="text-[10px] font-bold text-neutral-400 mt-2 tracking-wider">4 HOURS AGO</p>
                  </div>
                </div>
                <div className="flex gap-4 group cursor-pointer">
                  <div className="w-10 h-10 rounded-2xl bg-primary-50 flex items-center justify-center text-primary shrink-0 mt-0.5 border border-primary-100 shadow-sm group-hover:scale-110 transition-transform">
                    <i className="ph-fill ph-plus-circle text-lg"></i>
                  </div>
                  <div>
                    <p className="text-sm font-black text-neutral-900 leading-tight group-hover:text-primary transition-colors">New Asset Registered</p>
                    <p className="text-xs text-neutral-500 mt-1.5 font-medium leading-relaxed">Conveyor Belt System v3 added to Assembly Line B.</p>
                    <p className="text-[10px] font-bold text-neutral-400 mt-2 tracking-wider">YESTERDAY</p>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};
