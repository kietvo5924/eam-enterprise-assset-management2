import { create } from 'zustand';
import api from '../../../utils/axios';

export interface PmPlanChecklist {
  id?: string;
  itemName: string;
  inputType: 'PASS_FAIL' | 'TEXT' | 'NUMBER';
  expectedValue?: string;
  isMandatory: boolean;
}

export interface PmPlanMaterial {
  id?: string;
  sparePartId: string;
  sparePartName?: string;
  quantity: number;
}

export interface PmPlan {
  id: string;
  name: string;
  description?: string;
  triggerType: 'TIME' | 'USAGE' | 'METER';
  intervalValue?: number;
  intervalUnit?: 'DAYS' | 'WEEKS' | 'MONTHS' | 'YEARS';
  isActive: boolean;
  isFloatingSchedule?: boolean;
  suppressIfPending?: boolean;
  leadTimeDays?: number;
  estimatedDurationMinutes?: number;
  assigneeId?: string;
  assignee?: {
    id: string;
    username: string;
    fullName?: string;
  };
  checklists?: PmPlanChecklist[];
  materials?: PmPlanMaterial[];
}

export interface PmPlanAssignment {
  id: string;
  pmPlanId: string;
  assetId: string;
  assetName: string;
  baselineMeterReading: number;
  status: 'ACTIVE' | 'PAUSED' | 'DEACTIVATED';
}

export interface MaintenanceKpi {
  totalPlans: number;
  upcomingIn7Days: number;
  missedPms: number;
  complianceRate: number;
}

interface PmPlanStore {
  pmPlans: PmPlan[];
  kpis: MaintenanceKpi | null;
  isLoading: boolean;
  
  fetchPmPlans: () => Promise<void>;
  fetchMaintenanceKpis: () => Promise<void>;
  createPmPlan: (data: Partial<PmPlan>) => Promise<boolean>;
  updatePmPlan: (id: string, data: Partial<PmPlan>) => Promise<boolean>;
  deletePmPlan: (id: string) => Promise<boolean>;
  assignPmPlanToAssets: (id: string, assetIds: string[]) => Promise<boolean>;
  fetchAssignments: (planId: string) => Promise<PmPlanAssignment[]>;
  deleteAssignment: (assignmentId: string) => Promise<boolean>;
  updateAssignmentStatus: (assignmentId: string, status: 'ACTIVE' | 'PAUSED' | 'DEACTIVATED') => Promise<boolean>;
}

export const usePmPlanStore = create<PmPlanStore>((set) => ({
  pmPlans: [],
  kpis: null,
  isLoading: false,

  fetchPmPlans: async () => {
    set({ isLoading: true });
    try {
      const response = await api.get('/pm-plans');
      if (response.data.success) {
        set({ pmPlans: response.data.data });
      }
    } catch (error) {
      console.error('Failed to fetch PM Plans:', error);
    } finally {
      set({ isLoading: false });
    }
  },

  fetchMaintenanceKpis: async () => {
    try {
      const response = await api.get('/pm-plans/kpis');
      if (response.data.success) {
        set({ kpis: response.data.data });
      }
    } catch (error) {
      console.error('Failed to fetch Maintenance KPIs:', error);
    }
  },

  createPmPlan: async (data) => {
    try {
      const response = await api.post('/pm-plans', data);
      if (response.data.success) {
        set(state => ({ pmPlans: [...state.pmPlans, response.data.data] }));
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to create PM Plan:', error);
      throw error;
    }
  },

  updatePmPlan: async (id, data) => {
    try {
      const response = await api.put(`/pm-plans/${id}`, data);
      if (response.data.success) {
        set(state => ({ pmPlans: state.pmPlans.map(p => p.id === id ? response.data.data : p) }));
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to update PM Plan:', error);
      throw error;
    }
  },

  deletePmPlan: async (id) => {
    try {
      const response = await api.delete(`/pm-plans/${id}`);
      if (response.data.success) {
        set(state => ({ pmPlans: state.pmPlans.filter(p => p.id !== id) }));
        return true;
      }
      return false;
    } catch (error: any) {
      if (error.response?.data?.message) {
        throw new Error(error.response.data.message);
      }
      console.error('Failed to delete PM Plan:', error);
      return false;
    }
  },

  assignPmPlanToAssets: async (id, assetIds) => {
    try {
      const response = await api.post(`/pm-plans/${id}/assign`, { assetIds });
      return response.data.success;
    } catch (error) {
      console.error('Failed to assign PM Plan to assets:', error);
      throw error;
    }
  },

  fetchAssignments: async (planId: string) => {
    try {
      const response = await api.get(`/pm-plans/${planId}/assignments`);
      if (response.data.success) {
        return response.data.data;
      }
      return [];
    } catch (error) {
      console.error('Failed to fetch assignments:', error);
      return [];
    }
  },

  deleteAssignment: async (assignmentId: string) => {
    try {
      const response = await api.delete(`/pm-plans/assignments/${assignmentId}`);
      return response.data.success;
    } catch (error: any) {
      if (error.response?.data?.message) {
        throw new Error(error.response.data.message);
      }
      console.error('Failed to delete assignment:', error);
      return false;
    }
  },

  updateAssignmentStatus: async (assignmentId, status) => {
    try {
      const response = await api.patch(`/pm-plans/assignments/${assignmentId}/status`, { status });
      return response.data.success;
    } catch (error) {
      console.error('Failed to update assignment status:', error);
      return false;
    }
  }
}));
