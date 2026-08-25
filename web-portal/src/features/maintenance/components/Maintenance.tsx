import React, { useState } from 'react';
import { Modal, Button } from 'antd';
import { PlusOutlined, LinkOutlined } from '@ant-design/icons';
import { usePmPlanStore } from '../store/usePmPlanStore';
import { CreatePmPlanForm } from './CreatePmPlanForm';
import { AssignPmPlanModal } from './AssignPmPlanModal';
import { MaintenanceCalendar } from './MaintenanceCalendar';
import { MaintenanceList } from './MaintenanceList';
import { PmPlansTable } from './PmPlansTable';

export const Maintenance: React.FC = () => {
  const [isCreateModalVisible, setIsCreateModalVisible] = useState(false);
  const [isAssignModalVisible, setIsAssignModalVisible] = useState(false);
  const [viewMode, setViewMode] = useState<'calendar' | 'list' | 'plans'>(() => {
    return (localStorage.getItem('maintenanceViewMode') as 'calendar' | 'list' | 'plans') || 'calendar';
  });

  const { kpis, fetchMaintenanceKpis } = usePmPlanStore();

  React.useEffect(() => {
    localStorage.setItem('maintenanceViewMode', viewMode);
  }, [viewMode]);

  React.useEffect(() => {
    fetchMaintenanceKpis();
  }, [fetchMaintenanceKpis]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-[0.18em] mb-1">PLANNING</p>
          <h2 className="text-[26px] leading-tight font-black text-neutral-900 tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-50 rounded-xl flex items-center justify-center text-primary text-2xl shrink-0">
              <i className="ph-fill ph-calendar-check"></i>
            </div>
            Preventive Maintenance
            Preventive Maintenance
          </h2>
        </div>
        <div className="flex items-center gap-2 opacity-70">
          <div className="flex bg-white border border-neutral-200 rounded-lg p-1 shadow-sm">
            <button 
              onClick={() => setViewMode('calendar')} 
              className={`px-3 py-1.5 rounded-md text-sm font-bold shadow-sm ${viewMode === 'calendar' ? 'bg-primary-50 text-primary' : 'text-neutral-500 hover:bg-neutral-50'}`}
            >
              Calendar
            </button>
            <button 
              onClick={() => setViewMode('list')} 
              className={`px-3 py-1.5 rounded-md text-sm font-bold shadow-sm ${viewMode === 'list' ? 'bg-primary-50 text-primary' : 'text-neutral-500 hover:bg-neutral-50'}`}
            >
              List
            </button>
            <button 
              onClick={() => setViewMode('plans')} 
              className={`px-3 py-1.5 rounded-md text-sm font-bold shadow-sm ${viewMode === 'plans' ? 'bg-primary-50 text-primary' : 'text-neutral-500 hover:bg-neutral-50'}`}
            >
              Plans
            </button>
          </div>
          <Button
            onClick={() => setIsAssignModalVisible(true)}
            icon={<LinkOutlined />}
            className="rounded-xl h-10 px-4 font-semibold text-neutral-700 flex items-center gap-2 shadow-sm">
            Assign Plan
          </Button>
          <Button
            type="primary"
            onClick={() => setIsCreateModalVisible(true)}
            icon={<PlusOutlined />}
            className="rounded-xl h-10 px-5 font-bold flex items-center justify-center gap-2 shadow-sm">
            New Plan
          </Button>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6">
        {[
          { label: 'Total Plans', value: kpis?.totalPlans ?? '-', icon: 'ph-calendar-check', color: 'text-primary', bg: 'bg-primary-50', border: 'border-primary-100', trend: '' },
          { label: 'Upcoming (7d)', value: kpis?.upcomingIn7Days ?? '-', icon: 'ph-clock-countdown', color: 'text-warning', bg: 'bg-orange-50', border: 'border-orange-100', trend: '' },
          { label: 'Missed PMs', value: kpis?.missedPms ?? '-', icon: 'ph-warning-circle', color: 'text-danger', bg: 'bg-red-50', border: 'border-red-100', trend: '' },
          { label: 'Compliance Rate', value: kpis ? `${kpis.complianceRate.toFixed(1)}%` : '-', icon: 'ph-check-circle', color: 'text-success', bg: 'bg-green-50', border: 'border-green-100', trend: '' }
        ].map((kpi, idx) => (
          <div key={idx} className="bg-white p-5 rounded-2xl border border-neutral-200 shadow-[0_2px_10px_rgba(0,0,0,0.02)] hover:shadow-md transition relative overflow-hidden group">
            <div className="flex justify-between items-start mb-4 relative z-10">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl ${kpi.bg} ${kpi.color}`}>
                <i className={`ph-fill ${kpi.icon}`}></i>
              </div>
              {kpi.trend && (
                <span className={`text-[10px] font-bold px-2 py-1 rounded-md uppercase tracking-wider ${kpi.trend.startsWith('+') ? (kpi.label === 'Upcoming (7d)' ? 'bg-orange-50 text-orange-700' : 'bg-green-50 text-green-700') : 'bg-neutral-100 text-neutral-600'}`}>
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

      {/* Main Content Area */}
      <div className="flex-1 min-h-[500px]">
        {viewMode === 'calendar' && <MaintenanceCalendar />}
        {viewMode === 'list' && <MaintenanceList />}
        {viewMode === 'plans' && <PmPlansTable />}
      </div>

      {/* Create Modal */}
      <Modal
        title="Create Preventive Maintenance Plan"
        open={isCreateModalVisible}
        onCancel={() => setIsCreateModalVisible(false)}
        footer={null}
        destroyOnHidden={true}
        width={600}
      >
        <CreatePmPlanForm
          onCancel={() => setIsCreateModalVisible(false)}
          onSuccess={() => setIsCreateModalVisible(false)}
        />
      </Modal>

      <AssignPmPlanModal
        visible={isAssignModalVisible}
        onCancel={() => setIsAssignModalVisible(false)}
        onSuccess={() => setIsAssignModalVisible(false)}
      />
    </div>
  );
};
