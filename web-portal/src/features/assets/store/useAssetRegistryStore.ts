import { create } from 'zustand';
import api from '../../../utils/axios';

export interface Asset {
  id: string;
  name: string;
  categoryId: string | null;
  categoryName: string | null;
  parentId: string | null;
  serialNumber: string | null;
  model: string | null;
  manufacturer: string | null;
  purchaseDate: string | null;
  value: number | null;
  status: 'OPERATIONAL' | 'MAINTENANCE' | 'BROKEN' | 'DECOMMISSIONED' | 'RESERVED';
  locationId: string | null;
  locationName: string | null;
  hierarchyTemplateId: string | null;
  hierarchyTemplateName: string | null;
  qrCode: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  createdByName?: string;
  updatedByName?: string;
}

export interface AssetCreateRequest {
  name: string;
  categoryId?: string;
  hierarchyTemplateId?: string;
  serialNumber?: string;
  model?: string;
  manufacturer?: string;
  purchaseDate?: string;
  value?: number;
  status?: 'OPERATIONAL' | 'MAINTENANCE' | 'BROKEN' | 'DECOMMISSIONED' | 'RESERVED';
  locationId?: string;
  isActive?: boolean;
}

interface AssetRegistryState {
  assets: Asset[];
  treeData: any | null; // For holding backend tree response
  loading: boolean;
  fetchAssets: (page?: number, size?: number) => Promise<void>;
  fetchAssetTree: (search?: string, status?: string, categoryId?: string) => Promise<void>;
  createAsset: (data: AssetCreateRequest) => Promise<boolean>;
  updateAsset: (id: string, data: Partial<AssetCreateRequest>) => Promise<boolean>;
  deleteAsset: (id: string) => Promise<boolean>;
  importAssets: (file: File) => Promise<any>;
  exportAssets: () => Promise<void>;
}

export const useAssetRegistryStore = create<AssetRegistryState>((set) => ({
  assets: [],
  treeData: null,
  loading: false,

  fetchAssets: async (page = 0, size = 100) => {
    set({ loading: true });
    try {
      const response = await api.get(`/assets?page=${page}&size=${size}`);
      set({ assets: response.data.data.content, loading: false });
    } catch (error) {
      set({ loading: false });
      console.error('Failed to fetch assets', error);
      throw error;
    }
  },

  fetchAssetTree: async (search = '', status = '', categoryId = '') => {
    set({ loading: true });
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (status) params.append('status', status);
      if (categoryId) params.append('categoryId', categoryId);
      
      const response = await api.get(`/assets/tree?${params.toString()}`);
      set({ treeData: response.data.data, loading: false });
    } catch (error) {
      set({ loading: false });
      console.error('Failed to fetch asset tree', error);
      throw error;
    }
  },

  importAssets: async (file: File) => {
    set({ loading: true });
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await api.post('/assets/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      set({ loading: false });
      return response.data;
    } catch (error) {
      set({ loading: false });
      throw error;
    }
  },

  exportAssets: async () => {
    try {
      const response = await api.get('/assets/export', { responseType: 'text' });
      return response.data;
    } catch (error) {
      console.error('Failed to export assets', error);
      throw error;
    }
  },

  createAsset: async (data) => {
    try {
      const response = await api.post('/assets', data);
      const newAsset = response.data.data;
      set((state) => ({ assets: [newAsset, ...state.assets] }));
      return true;
    } catch (error) {
      console.error('Failed to create asset', error);
      throw error;
    }
  },

  updateAsset: async (id, data) => {
    try {
      const response = await api.put(`/assets/${id}`, data);
      const updatedAsset = response.data.data;
      set((state) => ({
        assets: state.assets.map((asset) => (asset.id === id ? updatedAsset : asset)),
      }));
      return true;
    } catch (error) {
      console.error('Failed to update asset', error);
      throw error;
    }
  },

  deleteAsset: async (id) => {
    try {
      await api.delete(`/assets/${id}`);
      set((state) => ({
        assets: state.assets.filter((asset) => asset.id !== id),
      }));
      return true;
    } catch (error) {
      console.error('Failed to delete asset', error);
      throw error;
    }
  },
}));
