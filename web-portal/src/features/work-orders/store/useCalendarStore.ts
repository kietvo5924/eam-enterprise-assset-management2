import { create } from 'zustand';
import { workOrderApi } from '../api/workOrderApi';
import dayjs, { Dayjs } from 'dayjs';

export interface CalendarEvent {
  id: string;
  title: string;
  eventDate: string;
  eventType: 'WORK_ORDER' | 'PM_PLAN';
  status: string;
  assetId: string;
  assetName: string;
  priority: string;
  originalData?: any;
}

interface CalendarFilters {
  assetId?: string;
  categoryId?: string;
  status?: string;
}

interface CalendarState {
  events: CalendarEvent[];
  isLoading: boolean;
  error: string | null;
  currentDate: Dayjs;
  filters: CalendarFilters;
  mode: 'month' | 'year';
  
  // Actions
  fetchEvents: (startDate: string, endDate: string) => Promise<void>;
  setCurrentDate: (date: Dayjs) => void;
  setMode: (mode: 'month' | 'year') => void;
  setFilters: (filters: CalendarFilters) => void;
  clearFilters: () => void;
}

export const useCalendarStore = create<CalendarState>((set, get) => ({
  events: [],
  isLoading: false,
  error: null,
  currentDate: dayjs(localStorage.getItem('maintenanceCurrentDate') || undefined),
  mode: (localStorage.getItem('maintenanceCalendarMode') as 'month' | 'year') || 'month',
  filters: {},
  abortController: null as AbortController | null,

  fetchEvents: async (startDate: string, endDate: string) => {
    const currentState = get() as any;
    if (currentState.abortController) {
      currentState.abortController.abort();
    }
    const abortController = new AbortController();
    set({ isLoading: true, error: null, abortController } as any);
    try {
      const filters = get().filters;
      const response = await workOrderApi.getCalendarEvents(startDate, endDate, filters.assetId, filters.categoryId, filters.status);
      if (response.data.success) {
        set({ events: response.data.data });
      } else {
        set({ error: response.data.error?.message || 'Failed to fetch calendar events' });
      }
    } catch (err: any) {
      if (err.name === 'CanceledError' || err.message === 'canceled') return; // Ignore canceled requests
      set({ error: err.response?.data?.error?.message || err.message || 'An error occurred' });
    } finally {
      const state = get() as any;
      if (state.abortController === abortController) {
        set({ isLoading: false, abortController: null } as any);
      }
    }
  },

  setCurrentDate: (date: Dayjs) => {
    set({ currentDate: date });
    localStorage.setItem('maintenanceCurrentDate', date.toISOString());
  },

  setMode: (mode: 'month' | 'year') => {
    set({ mode });
    localStorage.setItem('maintenanceCalendarMode', mode);
  },

  setFilters: (filters: CalendarFilters) => {
    set((state) => ({ filters: { ...state.filters, ...filters } }));
  },

  clearFilters: () => {
    set({ filters: {} });
  }
}));
