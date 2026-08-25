import React from 'react';

export const Reports: React.FC = () => {
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      
      {/* Feature Under Development Banner */}
      <div className="mb-6 bg-warning/10 border border-warning/20 rounded-xl p-4 flex items-center gap-4 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-warning/5 rounded-full blur-2xl -mr-10 -mt-10 pointer-events-none"></div>
        <div className="w-10 h-10 bg-warning/20 rounded-full flex items-center justify-center shrink-0">
          <i className="ph-fill ph-warning-circle text-warning text-xl animate-pulse"></i>
        </div>
        <div>
          <h3 className="font-bold text-neutral-900 text-sm">Tính Năng Đang Phát Triển</h3>
          <p className="text-neutral-600 text-xs mt-0.5">Phân hệ Báo cáo (System Reports) đang trong quá trình hoàn thiện. Các chức năng và nút bấm hiện tại chỉ mang tính chất minh họa giao diện.</p>
        </div>
      </div>

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-[0.18em] mb-1">ANALYTICS</p>
          <h2 className="text-[26px] leading-tight font-black text-neutral-900 tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-50 rounded-xl flex items-center justify-center text-primary text-2xl shrink-0">
              <i className="ph-fill ph-chart-line-up"></i>
            </div>
            System Reports
            <span className="text-[10px] bg-warning text-white px-2 py-1 rounded-md ml-2 align-middle font-bold">Đang phát triển</span>
          </h2>
        </div>
        <div className="flex items-center gap-2 opacity-70">
          <button className="px-4 py-2 bg-white border border-neutral-200 text-neutral-700 font-bold text-sm rounded-lg flex items-center gap-1.5 shadow-sm cursor-not-allowed">
            <i className="ph-bold ph-calendar"></i> Date Range (Đang phát triển)
          </button>
          <button className="px-4 py-2 bg-primary text-white font-bold text-sm rounded-lg flex items-center gap-1.5 shadow-sm shadow-primary/30 cursor-not-allowed">
            <i className="ph-bold ph-download-simple"></i> Export PDF (Đang phát triển)
          </button>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6">
        {[
          { label: 'Total Reports', value: '124', icon: 'ph-file-text', color: 'text-primary', bg: 'bg-primary-50', border: 'border-primary-100', trend: '+12' },
          { label: 'Avg Uptime', value: '98.2%', icon: 'ph-activity', color: 'text-success', bg: 'bg-green-50', border: 'border-green-100', trend: '+0.5%' },
          { label: 'Total Cost', value: '$45K', icon: 'ph-currency-dollar', color: 'text-warning', bg: 'bg-orange-50', border: 'border-orange-100', trend: '-2.4%' },
          { label: 'Critical Assets', value: '18', icon: 'ph-warning-circle', color: 'text-danger', bg: 'bg-red-50', border: 'border-red-100', trend: '-1' }
        ].map((kpi, idx) => (
          <div key={idx} className="bg-white p-5 rounded-2xl border border-neutral-200 shadow-[0_2px_10px_rgba(0,0,0,0.02)] hover:shadow-md transition relative overflow-hidden group">
            <div className="flex justify-between items-start mb-4 relative z-10">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl ${kpi.bg} ${kpi.color}`}>
                <i className={`ph-fill ${kpi.icon}`}></i>
              </div>
              <span className={`text-[10px] font-bold px-2 py-1 rounded-md uppercase tracking-wider ${kpi.trend.startsWith('+') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
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

      <div className="bg-white border border-neutral-200 rounded-3xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] flex flex-col h-full overflow-hidden">
        
        <div className="p-4 border-b border-neutral-200 shrink-0 flex justify-between items-center bg-white">
          <div className="flex items-center gap-4">
            <h3 className="font-bold text-lg">Monthly Analytics</h3>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-neutral-100 rounded-lg p-1">
              <button className="px-3 py-1.5 bg-white shadow-sm rounded-md text-sm font-bold text-neutral-800">Charts</button>
              <button className="px-3 py-1.5 rounded-md text-sm font-medium text-neutral-500 hover:text-neutral-700">Data Grid</button>
            </div>
            <button className="px-3 py-1.5 border border-neutral-200 text-neutral-600 font-bold text-sm hover:bg-neutral-50 rounded-lg flex items-center gap-1.5 transition-colors">
              <i className="ph-bold ph-funnel"></i> Filters
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto bg-neutral-50 p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm">
              <h3 className="font-bold text-neutral-800 mb-6">Asset Downtime by Category</h3>
              <div className="flex justify-center items-center h-64 relative">
                {/* Fake Donut Chart */}
                <svg viewBox="0 0 100 100" className="w-48 h-48 transform -rotate-90">
                  <circle cx="50" cy="50" r="40" fill="transparent" stroke="#e2e8f0" strokeWidth="20" />
                  <circle cx="50" cy="50" r="40" fill="transparent" stroke="#00a0e2" strokeWidth="20" strokeDasharray="251.2" strokeDashoffset="60" />
                  <circle cx="50" cy="50" r="40" fill="transparent" stroke="#faad14" strokeWidth="20" strokeDasharray="251.2" strokeDashoffset="190" />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-2xl font-black text-neutral-900">45</span>
                  <span className="text-[10px] font-bold text-neutral-400">HOURS</span>
                </div>
              </div>
              <div className="flex justify-center gap-4 mt-4">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600"><span className="w-3 h-3 rounded-full bg-primary"></span> Mechanical</div>
                <div className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600"><span className="w-3 h-3 rounded-full bg-warning"></span> Electrical</div>
              </div>
            </div>

            <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm">
              <h3 className="font-bold text-neutral-800 mb-6">Maintenance Cost Trend</h3>
              <div className="flex justify-center items-center h-64">
                {/* Fake Bar Chart */}
                <div className="flex items-end gap-2 w-full h-full px-4">
                  {[40, 60, 30, 80, 50, 90, 70].map((h, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center gap-2 group cursor-pointer">
                      <div className="w-full bg-primary-100 rounded-t-sm group-hover:bg-primary transition-colors relative" style={{ height: `${h}%` }}>
                         <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-neutral-800 text-white text-[10px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 pointer-events-none">
                            ${h * 120}
                         </div>
                      </div>
                      <span className="text-[10px] font-bold text-neutral-400">M{i+1}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};
