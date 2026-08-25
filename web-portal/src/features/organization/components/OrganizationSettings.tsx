import React, { useEffect, useState } from 'react';
import { message, Spin } from 'antd';
import api from '../../../utils/axios';
import { useTenantStore } from '../../../app/store/useTenantStore';
import { formatToTenantTimezone } from '../../../utils/dateUtils';

interface SettingsFormValues {
  name: string;
  logoUrl: string;
  timezone: string;
}

const timezones = [
  'UTC',
  'Asia/Ho_Chi_Minh',
  'America/New_York',
  'Europe/London',
  'Asia/Tokyo',
];

export const OrganizationSettings: React.FC = () => {
  const [formData, setFormData] = useState<SettingsFormValues>({ name: '', logoUrl: '', timezone: 'UTC' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const { setSettings } = useTenantStore();

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await api.get('/tenant/settings');
      if (response.data.success) {
        const data = response.data.data;
        setFormData(data);
        setSettings(data);
      } else {
        message.error(response.data.error || 'Failed to load settings');
      }
    } catch (error: any) {
      if (error.response?.status !== 403) {
        message.error('Failed to load settings');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const response = await api.put('/tenant/settings', formData);
      if (response.data.success) {
        message.success('Settings updated successfully');
        setSettings(response.data.data);
      } else {
        message.error(response.data.error || 'Failed to update settings');
      }
    } catch (error: any) {
      if (error.response?.status !== 403) {
        message.error('Failed to update settings');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.size > 2 * 1024 * 1024) {
        message.error('File must be smaller than 2MB');
        return;
      }

      const formDataUpload = new FormData();
      formDataUpload.append('file', file);

      setUploadingLogo(true);
      try {
        const response = await api.post('/files/upload/logo', formDataUpload, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });
        if (response.data.success) {
          setFormData({ ...formData, logoUrl: response.data.data.url });
          message.success("Logo uploaded successfully. Don't forget to save changes.");
        } else {
          message.error(response.data.error || 'Failed to upload logo');
        }
      } catch (error: any) {
        message.error('Failed to upload logo');
      } finally {
        setUploadingLogo(false);
        // Reset file input
        e.target.value = '';
      }
    }
  };

  if (loading) return (
    <div className="flex justify-center items-center h-64">
      <Spin size="large" />
    </div>
  );

  const exampleUtc = new Date().toISOString();

  return (
    <div className="max-w-[1200px] mx-auto py-8 px-4 h-full">
      <div className="bg-white backdrop-blur-2xl rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.08)] border border-neutral-200/60 overflow-hidden relative transition flex flex-col min-h-[600px]">
        {/* Magic Background Elements */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary-300 via-primary-500 to-primary-600"></div>
        <div className="absolute top-0 right-0 w-[800px] h-[800px] rounded-full bg-gradient-to-bl from-primary-100/40 via-info/10 to-transparent blur-3xl opacity-80 pointer-events-none"></div>
        <div className="absolute bottom-0 left-0 w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-success/5 via-primary-50/20 to-transparent blur-3xl opacity-80 pointer-events-none"></div>

        {/* Top Header Bar */}
        <div className="w-full p-4 md:p-5 border-b border-neutral-100/80 bg-white/40 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-4 shrink-0 relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-gear text-xl"></i>
            </div>
            <div>
              <h2 className="text-xl font-black text-transparent bg-clip-text bg-gradient-to-r from-neutral-900 to-neutral-600 tracking-tight m-0">Settings & Preferences</h2>
              <p className="text-xs font-medium text-neutral-500 m-0 mt-0.5">Customize how your organization appears and operates across the system.</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm font-bold text-neutral-500 bg-neutral-50/80 px-4 py-2 rounded-lg border border-neutral-100 shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
            <i className="ph-fill ph-buildings text-primary"></i>
            <span>Organization Profile</span>
          </div>
        </div>

        <div className="flex flex-col md:flex-row flex-1 relative z-10">
          {/* Left Sidebar Profile View */}
          <div className="w-full md:w-[380px] bg-neutral-50/80 border-r border-neutral-200/80 p-8 flex flex-col items-center justify-center text-center shrink-0">
            <div className="relative group cursor-pointer mb-6">
              <div className="w-32 h-32 rounded-full border-4 border-white shadow-[0_8px_30px_rgba(0,0,0,0.1)] overflow-hidden bg-white flex items-center justify-center relative z-10 transition-transform duration-500 group-hover:scale-105">
                {formData.logoUrl ? (
                  <img src={formData.logoUrl} alt="Organization Logo" className="w-full h-full object-cover" onError={(e) => (e.currentTarget.style.display = 'none')} />
                ) : (
                  <div className="w-full h-full bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center">
                    <i className="ph-fill ph-buildings text-5xl text-primary/50"></i>
                  </div>
                )}
              </div>
              <div className="absolute inset-0 rounded-full bg-primary/20 blur-xl scale-110 group-hover:scale-125 transition-transform duration-500 -z-10 opacity-0 group-hover:opacity-100"></div>
            </div>

            <h2 className="text-2xl font-black text-neutral-900 m-0 mb-2 truncate w-full px-4">{formData.name || 'Your Organization'}</h2>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-success/10 text-success font-bold text-xs rounded-full border border-success/20">
              <i className="ph-fill ph-check-circle"></i> Active Tenant
            </div>

            <div className="mt-10 w-full text-left space-y-4">
              <div className="bg-white p-4 rounded-2xl shadow-sm border border-neutral-100 flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-info/10 text-info flex items-center justify-center shrink-0">
                  <i className="ph-fill ph-clock text-xl"></i>
                </div>
                <div>
                  <p className="text-xs font-bold text-neutral-400 uppercase tracking-wider m-0">Timezone</p>
                  <p className="text-sm font-bold text-neutral-800 m-0 mt-0.5">{formData.timezone || 'Not Set'}</p>
                </div>
              </div>

              <div className="bg-white p-4 rounded-2xl shadow-sm border border-neutral-100 flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary-50 text-primary flex items-center justify-center shrink-0">
                  <i className="ph-fill ph-calendar text-xl"></i>
                </div>
                <div>
                  <p className="text-xs font-bold text-neutral-400 uppercase tracking-wider m-0">Current Local Time</p>
                  <p className="text-sm font-bold text-neutral-800 m-0 mt-0.5 font-mono">{formatToTenantTimezone(exampleUtc, formData.timezone || 'UTC')}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Form section */}
          <div className="flex-1 flex flex-col bg-white/50">
            <div className="flex-1 overflow-y-auto">
              <form onSubmit={handleSubmit} className="p-10 space-y-8">

                {/* Organization Name */}
                <div className="group">
                  <label className="block text-sm font-extrabold text-neutral-700 uppercase tracking-wide mb-2 flex items-center gap-2">
                    <i className="ph-fill ph-text-t text-primary"></i>
                    Organization Name <span className="text-danger">*</span>
                  </label>
                  <input
                    type="text"
                    name="name"
                    required
                    value={formData.name}
                    onChange={handleChange}
                    placeholder="e.g. Acme Corporation"
                    className="w-full px-5 h-14 bg-white border border-neutral-200/80 rounded-xl text-base focus:outline-none focus:border-primary focus:ring-4 focus:ring-primary/10 transition font-semibold text-neutral-900 shadow-sm group-hover:border-neutral-300"
                  />
                  <p className="text-xs font-medium text-neutral-500 mt-2 ml-1">This name will be displayed on reports, dashboards, and emails sent to users.</p>
                </div>

                {/* Logo URL */}
                <div className="group">
                  <label className="block text-sm font-extrabold text-neutral-700 uppercase tracking-wide mb-2 flex items-center gap-2">
                    <i className="ph-fill ph-image text-primary"></i>
                    Brand Logo URL
                  </label>
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <input
                        type="url"
                        name="logoUrl"
                        value={formData.logoUrl || ''}
                        onChange={handleChange}
                        placeholder="https://example.com/logo.png"
                        className="w-full px-5 h-14 bg-white border border-neutral-200/80 rounded-xl text-base focus:outline-none focus:border-primary focus:ring-4 focus:ring-primary/10 transition font-semibold text-neutral-900 shadow-sm group-hover:border-neutral-300"
                      />
                    </div>
                    <div className="shrink-0">
                      <label
                        className={`px-6 h-14 bg-gradient-to-br from-neutral-50 to-neutral-100 hover:from-white hover:to-neutral-50 text-neutral-800 rounded-xl font-black text-sm shadow-[0_4px_10px_rgba(0,0,0,0.05)] transition-all active:scale-[0.98] flex items-center gap-2.5 border border-neutral-200/80 hover:border-neutral-300 hover:shadow-[0_8px_20px_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transform-gpu cursor-pointer ${uploadingLogo ? 'opacity-70 pointer-events-none' : ''}`}
                      >
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleLogoUpload}
                          className="hidden"
                          disabled={uploadingLogo}
                        />
                        {uploadingLogo ? (
                          <><i className="ph-bold ph-spinner animate-spin text-lg text-primary"></i> <span className="tracking-wide">UPLOADING...</span></>
                        ) : (
                          <><i className="ph-bold ph-upload-simple text-lg text-primary"></i> <span className="tracking-wide">UPLOAD</span></>
                        )}
                      </label>
                    </div>
                  </div>
                  <p className="text-xs font-medium text-neutral-500 mt-2 ml-1">Upload an image or provide a URL (recommended size: 256x256px, max 2MB).</p>
                </div>

                {/* Timezone */}
                <div className="group">
                  <label className="block text-sm font-extrabold text-neutral-700 uppercase tracking-wide mb-2 flex items-center gap-2">
                    <i className="ph-fill ph-globe text-primary"></i>
                    Default Timezone <span className="text-danger">*</span>
                  </label>
                  <div className="relative">
                    <select
                      name="timezone"
                      required
                      value={formData.timezone}
                      onChange={handleChange}
                      className="w-full px-5 h-14 bg-white border border-neutral-200/80 rounded-xl text-base focus:outline-none focus:border-primary focus:ring-4 focus:ring-primary/10 transition font-semibold text-neutral-900 appearance-none pr-12 shadow-sm group-hover:border-neutral-300 cursor-pointer"
                    >
                      {timezones.map(tz => (
                        <option key={tz} value={tz}>{tz}</option>
                      ))}
                    </select>
                    <div className="absolute inset-y-0 right-0 flex items-center pr-4 pointer-events-none text-neutral-400">
                      <i className="ph-bold ph-caret-down text-lg"></i>
                    </div>
                  </div>
                  <p className="text-xs font-medium text-neutral-500 mt-2 ml-1">All dates and times in the system will be displayed according to this timezone by default.</p>
                </div>

                <div className="pt-8 border-t border-neutral-100/80 flex items-center justify-between">
                  <div className="text-sm font-semibold text-neutral-500 flex items-center gap-2">
                    <i className="ph-fill ph-shield-check text-success text-xl"></i>
                    Changes apply immediately across all sessions.
                  </div>
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-8 h-14 bg-gradient-to-r from-primary to-primary-600 hover:from-primary-500 hover:to-primary-700 text-white rounded-xl font-black text-base shadow-[0_8px_20px_rgba(0,160,226,0.3)] transition active:scale-[0.98] disabled:opacity-70 disabled:active:scale-100 flex items-center gap-3 hover:-translate-y-1 transform-gpu hover:shadow-[0_12px_25px_rgba(0,160,226,0.4)]"
                  >
                    {saving ? (
                      <><i className="ph-bold ph-spinner animate-spin text-xl"></i> SAVING...</>
                    ) : (
                      <><i className="ph-bold ph-floppy-disk text-xl"></i> SAVE CHANGES</>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
