import { create } from 'zustand';

interface TenantSettings {
  name: string;
  logoUrl: string | null;
  timezone: string;
}

interface TenantStore {
  settings: TenantSettings | null;
  setSettings: (settings: TenantSettings) => void;
  clearSettings: () => void;
}

export const useTenantStore = create<TenantStore>((set) => ({
  settings: null,
  setSettings: (settings) => set({ settings }),
  clearSettings: () => set({ settings: null }),
}));
