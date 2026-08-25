import { create } from 'zustand';
import api from '../../../utils/axios';

export interface MeterReading {
  id: string;
  assetId: string;
  readingValue: number;
  readingDate: string;
  unit: string | null;
  remarks: string | null;
  createdBy: string;
  createdAt: string;
}

export interface MeterReadingCreateRequest {
  readingValue: number;
  readingDate: string;
  unit?: string;
  remarks?: string;
}

interface MeterReadingState {
  readings: MeterReading[];
  loading: boolean;
  fetchReadings: (assetId: string) => Promise<void>;
  createReading: (assetId: string, data: MeterReadingCreateRequest) => Promise<boolean>;
}

export const useMeterReadingStore = create<MeterReadingState>((set) => ({
  readings: [],
  loading: false,

  fetchReadings: async (assetId: string) => {
    set({ loading: true });
    try {
      const response = await api.get(`/assets/${assetId}/meter-readings`);
      set({ readings: response.data, loading: false });
    } catch (error) {
      set({ loading: false });
      console.error('Failed to fetch meter readings', error);
      throw error;
    }
  },

  createReading: async (assetId: string, data: MeterReadingCreateRequest) => {
    try {
      const response = await api.post(`/assets/${assetId}/meter-readings`, data);
      set((state) => ({ readings: [response.data, ...state.readings] }));
      return true;
    } catch (error) {
      console.error('Failed to create meter reading', error);
      throw error;
    }
  },
}));
