import React, { useEffect } from 'react';
import { useWorkOrderStore } from '../store/useWorkOrderStore';
import WorkOrderList from './WorkOrderList';

export const WorkOrders: React.FC = () => {
  const { kpis, fetchWorkOrderKpis } = useWorkOrderStore();

  useEffect(() => {
    fetchWorkOrderKpis();
  }, [fetchWorkOrderKpis]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-[0.18em] mb-1">OPERATIONS</p>
          <h2 className="text-[26px] leading-tight font-black text-neutral-900 tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-50 rounded-xl flex items-center justify-center text-primary text-2xl shrink-0">
              <i className="ph-fill ph-clipboard-text"></i>
            </div>
            Work Orders
          </h2>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6">
        {[
          { label: 'Total WOs', value: kpis?.totalWorkOrders ?? '-', icon: 'ph-clipboard-text', color: 'text-primary', bg: 'bg-primary-50', border: 'border-primary-100', trend: '' },
          { label: 'In Progress', value: kpis?.inProgressWorkOrders ?? '-', icon: 'ph-wrench', color: 'text-warning', bg: 'bg-orange-50', border: 'border-orange-100', trend: '' },
          { label: 'Overdue', value: kpis?.overdueWorkOrders ?? '-', icon: 'ph-warning-circle', color: 'text-danger', bg: 'bg-red-50', border: 'border-red-100', trend: '' },
          { label: 'Completed (YTD)', value: kpis?.completedWorkOrders ?? '-', icon: 'ph-check-circle', color: 'text-success', bg: 'bg-green-50', border: 'border-green-100', trend: '' }
        ].map((kpi, idx) => (
          <div key={idx} className="bg-white p-5 rounded-2xl border border-neutral-200 shadow-[0_2px_10px_rgba(0,0,0,0.02)] hover:shadow-md transition relative overflow-hidden group">
            <div className="flex justify-between items-start mb-4 relative z-10">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl ${kpi.bg} ${kpi.color}`}>
                <i className={`ph-fill ${kpi.icon}`}></i>
              </div>
              {kpi.trend && (
                <span className={`text-[10px] font-bold px-2 py-1 rounded-md uppercase tracking-wider ${kpi.trend.startsWith('+') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                  {kpi.trend}
                </span>
              )}
            </div>
            <div className="relative z-10">
              <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{kpi.label}</p>
              <h3 className="text-3xl font-black text-neutral-900 tracking-tight">{kpi.value}</h3>
            </div>
            <div className={`absolute -bottom-6 -right-6 w-24 h-24 rounded-full border-[12px] opacity-20 ${kpi.border} group-hover:scale-150 transition-transform duration-500 pointer-events-none`}></div>
          </div>
        ))}
      </div>

      <WorkOrderList />
    </div>
  );
};
