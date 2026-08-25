import { create } from 'zustand';
import { workOrderApi } from '../api/workOrderApi';
import type { WorkOrderCreateRequest } from '../api/workOrderApi';

export interface WorkOrderReference {
  id: string;
  title: string;
  status: string;
}

export interface WorkOrder {
  id: string;
  asset: any;
  title: string;
  description: string;
  priority: string;
  status: string;
  deadline: string;
  createdAt: string;
  creator: any;
  assignee: any;
  assignedAt: string;
  resolutionNotes?: string;
  checklists?: any[];
  attachments?: any[];
  parentWorkOrder?: WorkOrderReference;
  followUpWorkOrders?: WorkOrderReference[];
  estimatedDurationMinutes?: number;
  materials?: any[];
}

export interface WorkOrderKpi {
  totalWorkOrders: number;
  inProgressWorkOrders: number;
  overdueWorkOrders: number;
  completedWorkOrders: number;
}

interface WorkOrderStore {
  workOrders: WorkOrder[];
  totalElements: number;
  kpis: WorkOrderKpi | null;
  loading: boolean;
  error: string | null;

  fetchWorkOrders: (page?: number, size?: number) => Promise<void>;
  fetchWorkOrderKpis: () => Promise<void>;
  createWorkOrder: (data: WorkOrderCreateRequest) => Promise<boolean>;
  updateWorkOrder: (id: string, data: WorkOrderCreateRequest) => Promise<boolean>;
  deleteWorkOrder: (id: string) => Promise<boolean>;
  assignWorkOrder: (id: string, assigneeId: string) => Promise<boolean>;
  updateWorkOrderStatus: (id: string, status: string) => Promise<boolean>;
  updateChecklist: (id: string, itemName: string, isCompleted: boolean, actualValue?: string) => Promise<boolean>;
  updateNotes: (id: string, notes: string) => Promise<boolean>;
  uploadAttachment: (id: string, file: File) => Promise<boolean>;
  deleteChecklist: (id: string, checklistId: string) => Promise<boolean>;
  deleteAttachment: (id: string, attachmentId: string) => Promise<boolean>;
}

export const useWorkOrderStore = create<WorkOrderStore>((set) => ({
  workOrders: [],
  totalElements: 0,
  kpis: null,
  loading: false,
  error: null,

  fetchWorkOrders: async (page = 0, size = 20) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.getWorkOrders(page, size);
      if (response.data.success) {
        set({
          workOrders: response.data.data.content,
          totalElements: response.data.data.totalElements,
        });
      } else {
        set({ error: response.data.message || 'Failed to fetch work orders' });
      }
    } catch (error: any) {
      set({ error: error.message || 'Failed to fetch work orders' });
    } finally {
      set({ loading: false });
    }
  },

  fetchWorkOrderKpis: async () => {
    try {
      const response = await workOrderApi.getWorkOrderKpis();
      if (response.data.success) {
        set({ kpis: response.data.data });
      }
    } catch (error: any) {
      console.error('Failed to fetch work order KPIs', error);
    }
  },

  createWorkOrder: async (data: WorkOrderCreateRequest) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.createWorkOrder(data);
      if (response.data.success) {
        set((state) => ({
          workOrders: [response.data.data, ...state.workOrders],
          totalElements: state.totalElements + 1,
        }));
        return true;
      } else {
        set({ error: response.data.message || 'Failed to create work order' });
        return false;
      }
    } catch (error: any) {
      set({ error: error.response?.data?.message || error.message || 'Failed to create work order' });
      return false;
      return false;
    } finally {
      set({ loading: false });
    }
  },

  updateWorkOrder: async (id: string, data: WorkOrderCreateRequest) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.updateWorkOrder(id, data);
      if (response.data.success) {
        set((state) => ({
          workOrders: state.workOrders.map((wo) => wo.id === id ? response.data.data : wo),
        }));
        return true;
      } else {
        set({ error: response.data.message || 'Failed to update work order' });
        return false;
      }
    } catch (error: any) {
      set({ error: error.response?.data?.message || error.message || 'Failed to update work order' });
      return false;
    } finally {
      set({ loading: false });
    }
  },

  deleteWorkOrder: async (id: string) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.deleteWorkOrder(id);
      if (response.data.success) {
        set((state) => ({
          workOrders: state.workOrders.filter((wo) => wo.id !== id),
          totalElements: state.totalElements - 1,
        }));
        return true;
      } else {
        set({ error: response.data.message || 'Failed to delete work order' });
        return false;
      }
    } catch (error: any) {
      set({ error: error.response?.data?.message || error.message || 'Failed to delete work order' });
      return false;
    } finally {
      set({ loading: false });
    }
  },

  assignWorkOrder: async (id: string, assigneeId: string) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.assignWorkOrder(id, assigneeId);
      if (response.data.success) {
        set((state) => ({
          workOrders: state.workOrders.map((wo) =>
            wo.id === id ? response.data.data : wo
          ),
        }));
        return true;
      } else {
        set({ error: response.data.message || 'Failed to assign work order' });
        return false;
      }
    } catch (error: any) {
      set({ error: error.response?.data?.message || error.message || 'Failed to assign work order' });
      return false;
    } finally {
      set({ loading: false });
    }
  },

  updateWorkOrderStatus: async (id: string, status: string) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.updateWorkOrderStatus(id, status);
      if (response.data.success) {
        set((state) => ({
          workOrders: state.workOrders.map((wo) =>
            wo.id === id ? response.data.data : wo
          ),
        }));
        return true;
      } else {
        set({ error: response.data.message || 'Failed to update work order status' });
        return false;
      }
    } catch (error: any) {
      set({ error: error.response?.data?.message || error.message || 'Failed to update work order status' });
      return false;
    } finally {
      set({ loading: false });
    }
  },

  updateChecklist: async (id: string, itemName: string, isCompleted: boolean, actualValue?: string) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.updateChecklist(id, itemName, isCompleted, actualValue);
      if (response.data.success) {
        // We could just reload the current work order or fetch all again
        return true;
      }
      set({ error: response.data.message || 'Failed to update checklist' });
      return false;
    } catch (error: any) {
      set({ error: error.response?.data?.message || 'Failed to update checklist' });
      return false;
    } finally {
      set({ loading: false });
    }
  },

  updateNotes: async (id: string, notes: string) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.updateNotes(id, notes);
      if (response.data.success) {
        set((state) => ({
          workOrders: state.workOrders.map((wo) =>
            wo.id === id ? response.data.data : wo
          ),
        }));
        return true;
      }
      set({ error: response.data.message || 'Failed to update notes' });
      return false;
    } catch (error: any) {
      set({ error: error.response?.data?.message || 'Failed to update notes' });
      return false;
    } finally {
      set({ loading: false });
    }
  },

  uploadAttachment: async (id: string, file: File) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.uploadAttachment(id, file);
      if (response.data.success) {
        return true;
      }
      set({ error: response.data.message || 'Failed to upload attachment' });
      return false;
    } catch (error: any) {
      set({ error: error.response?.data?.message || 'Failed to upload attachment' });
      return false;
    } finally {
      set({ loading: false });
    }
  },

  deleteChecklist: async (id: string, checklistId: string) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.deleteChecklist(id, checklistId);
      if (response.data.success) {
        return true;
      }
      set({ error: response.data.message || 'Failed to delete checklist' });
      return false;
    } catch (error: any) {
      set({ error: error.response?.data?.message || 'Failed to delete checklist' });
      return false;
    } finally {
      set({ loading: false });
    }
  },

  deleteAttachment: async (id: string, attachmentId: string) => {
    set({ loading: true, error: null });
    try {
      const response = await workOrderApi.deleteAttachment(id, attachmentId);
      if (response.data.success) {
        return true;
      }
      set({ error: response.data.message || 'Failed to delete attachment' });
      return false;
    } catch (error: any) {
      set({ error: error.response?.data?.message || 'Failed to delete attachment' });
      return false;
    } finally {
      set({ loading: false });
    }
  },
}));
