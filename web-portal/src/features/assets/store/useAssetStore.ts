import { create } from 'zustand';
import api from '../../../utils/axios';

export interface AssetCategory {
  id: string;
  name: string;
  description: string;
  isActive: boolean;
}

export interface Location {
  id: string;
  name: string;
  description: string;
  parentId: string;
  isActive: boolean;
}

export interface HierarchyTemplate {
  id: string;
  name: string;
  path: string;
  description: string;
  isActive: boolean;
}

interface AssetStore {
  categories: AssetCategory[];
  templates: HierarchyTemplate[];
  locations: Location[];
  loadingCategories: boolean;
  loadingTemplates: boolean;
  loadingLocations: boolean;
  
  fetchCategories: () => Promise<void>;
  fetchTemplates: () => Promise<void>;
  fetchLocations: () => Promise<void>;
  
  createCategory: (data: Partial<AssetCategory>) => Promise<boolean>;
  updateCategory: (id: string, data: Partial<AssetCategory>) => Promise<boolean>;
  deleteCategory: (id: string) => Promise<boolean>;
  
  createTemplate: (data: Partial<HierarchyTemplate>) => Promise<boolean>;
  updateTemplate: (id: string, data: Partial<HierarchyTemplate>) => Promise<boolean>;
  deleteTemplate: (id: string) => Promise<boolean>;

  createLocation: (data: Partial<Location>) => Promise<boolean>;
  updateLocation: (id: string, data: Partial<Location>) => Promise<boolean>;
  deleteLocation: (id: string) => Promise<boolean>;
}

export const useAssetStore = create<AssetStore>((set) => ({
  categories: [],
  templates: [],
  locations: [],
  loadingCategories: false,
  loadingTemplates: false,
  loadingLocations: false,

  fetchCategories: async () => {
    set({ loadingCategories: true });
    try {
      const response = await api.get('/asset-categories', { params: { page: 0, size: 1000 } });
      if (response.data.success) {
        const data = response.data.data?.content ?? response.data.data ?? [];
        set({ categories: data });
      }
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    } finally {
      set({ loadingCategories: false });
    }
  },

  fetchTemplates: async () => {
    set({ loadingTemplates: true });
    try {
      const response = await api.get('/hierarchy-templates', { params: { page: 0, size: 1000 } });
      if (response.data.success) {
        const data = response.data.data?.content ?? response.data.data ?? [];
        set({ templates: data });
      }
    } catch (error) {
      console.error('Failed to fetch templates:', error);
    } finally {
      set({ loadingTemplates: false });
    }
  },

  fetchLocations: async () => {
    set({ loadingLocations: true });
    try {
      const response = await api.get('/locations', { params: { page: 0, size: 1000 } });
      if (response.data.success) {
        const data = response.data.data?.content ?? response.data.data ?? [];
        set({ locations: data });
      }
    } catch (error) {
      console.error('Failed to fetch locations:', error);
    } finally {
      set({ loadingLocations: false });
    }
  },

  createCategory: async (data) => {
    const response = await api.post('/asset-categories', data);
    if (response.data.success) {
      set(state => ({ categories: [...state.categories, response.data.data] }));
      return true;
    }
    return false;
  },

  updateCategory: async (id, data) => {
    const response = await api.put(`/asset-categories/${id}`, data);
    if (response.data.success) {
      set(state => ({ categories: state.categories.map(c => c.id === id ? response.data.data : c) }));
      return true;
    }
    return false;
  },

  deleteCategory: async (id) => {
    const response = await api.delete(`/asset-categories/${id}`);
    if (response.data.success) {
      set(state => ({ categories: state.categories.filter(c => c.id !== id) }));
      return true;
    }
    return false;
  },

  createTemplate: async (data) => {
    const response = await api.post('/hierarchy-templates', data);
    if (response.data.success) {
      set(state => ({ templates: [...state.templates, response.data.data] }));
      return true;
    }
    return false;
  },

  updateTemplate: async (id, data) => {
    const response = await api.put(`/hierarchy-templates/${id}`, data);
    if (response.data.success) {
      set(state => ({ templates: state.templates.map(c => c.id === id ? response.data.data : c) }));
      return true;
    }
    return false;
  },

  deleteTemplate: async (id) => {
    const response = await api.delete(`/hierarchy-templates/${id}`);
    if (response.data.success) {
      set(state => ({ templates: state.templates.filter(c => c.id !== id) }));
      return true;
    }
    return false;
  },

  createLocation: async (data) => {
    const response = await api.post('/locations', data);
    if (response.data.success) {
      set(state => ({ locations: [...state.locations, response.data.data] }));
      return true;
    }
    return false;
  },

  updateLocation: async (id, data) => {
    const response = await api.put(`/locations/${id}`, data);
    if (response.data.success) {
      set(state => ({ locations: state.locations.map(l => l.id === id ? response.data.data : l) }));
      return true;
    }
    return false;
  },

  deleteLocation: async (id) => {
    const response = await api.delete(`/locations/${id}`);
    if (response.data.success) {
      set(state => ({ locations: state.locations.filter(l => l.id !== id) }));
      return true;
    }
    return false;
  }
}));
