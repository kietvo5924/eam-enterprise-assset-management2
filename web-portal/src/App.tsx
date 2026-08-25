import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { useTenantStore } from './app/store/useTenantStore';
import { OrganizationSettings } from './features/organization/components/OrganizationSettings';
import { RoleManagement } from './features/roles/components/RoleManagement';
import { UserManagement } from './features/users/components/UserManagement';
import { Dashboard } from './features/dashboard/components/Dashboard';
import { AuditLogViewer } from './features/audit/components/AuditLogViewer';
import { AssetRegistry } from './features/assets/components/AssetRegistry';
import { AssetCategoryManagement } from './features/assets/components/AssetCategoryManagement';
import { WorkOrders } from './features/work-orders/components/WorkOrders';
import { Maintenance } from './features/maintenance/components/Maintenance';
import { Reports } from './features/reports/components/Reports';
import { SparePartsManagement } from './features/inventory/components/SparePartsManagement';
import { SystemTenants } from './features/system-admin/components/SystemTenants';
import { message, Modal, Form, Input, Dropdown } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import api from './utils/axios';
import './App.css';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const [forgotModalVisible, setForgotModalVisible] = useState(false);
  const [forgotStep, setForgotStep] = useState<'email' | 'code'>('email');
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotForm] = Form.useForm();

  const handleSendCode = async (values: any) => {
    setForgotLoading(true);
    try {
      await api.post('/auth/forgot-password', { email: values.email });
      message.success('If the email exists, a reset code has been sent.');
      setForgotStep('code');
    } catch (err) {
      message.error('Failed to request reset code');
    } finally {
      setForgotLoading(false);
    }
  };

  const handleResetPassword = async (values: any) => {
    setForgotLoading(true);
    try {
      await api.post('/auth/reset-password', { code: values.code, newPassword: values.newPassword });
      message.success('Password reset successfully. You can now login.');
      setForgotModalVisible(false);
      setForgotStep('email');
      forgotForm.resetFields();
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Failed to reset password');
    } finally {
      setForgotLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await api.post('/auth/login', { username, password });
      if (response.data.success) {
        sessionStorage.clear();
        localStorage.clear();
        localStorage.setItem('token', response.data.data.token);
        localStorage.setItem('username', username);
        localStorage.setItem('tenantId', response.data.data.tenantId || '');
        localStorage.setItem('roles', response.data.data.roles || '');
        localStorage.setItem('permissions', response.data.data.permissions || '');
        message.success('Logged in successfully');
        window.location.href = '/dashboard';
      } else {
        message.error(response.data.error || 'Login failed');
      }
    } catch (err: any) {
      message.error(err.response?.data?.error || err.response?.data?.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex justify-center items-center min-h-screen bg-neutral-50 px-4">
      <div className="w-full max-w-[400px] bg-white rounded-2xl shadow-xl border border-neutral-100 p-6 sm:p-8">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-primary rounded-xl flex items-center justify-center text-white text-2xl font-bold mx-auto mb-4 shadow-md shadow-primary/20">
            <i className="ph-fill ph-hexagon"></i>
          </div>
          <h2 className="text-2xl font-extrabold text-neutral-900 m-0 tracking-tight">Welcome Back</h2>
          <p className="text-neutral-500 mt-2 text-sm font-medium">Enter your credentials to access your account</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-bold text-neutral-700 mb-1.5">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2.5 bg-neutral-50 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all font-medium"
            />
          </div>
          <div>
            <label className="block text-sm font-bold text-neutral-700 mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 pr-10 bg-neutral-50 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all font-medium"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 focus:outline-none"
              >
                <i className={showPassword ? "ph ph-eye-slash" : "ph ph-eye"}></i>
              </button>
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 mt-4 bg-primary hover:bg-primary-hover text-white rounded-lg font-bold text-sm shadow-md shadow-primary/20 transition-all active:scale-[0.98] disabled:opacity-70 disabled:active:scale-100"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
          <div className="text-center mt-4">
            <button
              type="button"
              className="text-primary text-sm font-semibold hover:underline bg-transparent border-none cursor-pointer"
              onClick={() => setForgotModalVisible(true)}
            >
              Forgot Password?
            </button>
          </div>
        </form>
      </div>

      {/* Forgot Password Modal */}
      <Modal
        title="Reset Password"
        open={forgotModalVisible}
        onCancel={() => {
          setForgotModalVisible(false);
          setForgotStep('email');
          forgotForm.resetFields();
        }}
        footer={null}
        destroyOnHidden={true}
      >
        {forgotStep === 'email' && (
          <Form form={forgotForm} layout="vertical" onFinish={handleSendCode}>
            <Form.Item name="email" label="Enter your registered email" rules={[{ required: true, type: 'email' }]}>
              <Input placeholder="admin@example.com" />
            </Form.Item>
            <button type="submit" disabled={forgotLoading} className="w-full h-10 bg-primary text-white rounded-lg font-bold text-sm hover:bg-primary-hover transition-all">
              {forgotLoading ? 'Sending...' : 'Send Reset Code'}
            </button>
          </Form>
        )}
        {forgotStep === 'code' && (
          <Form form={forgotForm} layout="vertical" onFinish={handleResetPassword}>
            <Form.Item name="code" label="Enter 6-digit code from email" rules={[{ required: true }]}>
              <Input placeholder="123456" />
            </Form.Item>
            <Form.Item name="newPassword" label="New Password" rules={[{ required: true, min: 6 }]}>
              <Input.Password placeholder="Enter new password" />
            </Form.Item>
            <button type="submit" disabled={forgotLoading} className="w-full h-10 bg-primary text-white rounded-lg font-bold text-sm hover:bg-primary-hover transition-all">
              {forgotLoading ? 'Resetting...' : 'Reset Password'}
            </button>
          </Form>
        )}
      </Modal>
    </div>
  );
};

const AppShell: React.FC = () => {
  const { settings, setSettings } = useTenantStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [changePasswordVisible, setChangePasswordVisible] = useState(false);
  const [passwordForm] = Form.useForm();
  const location = useLocation();

  const handleLogout = React.useCallback(() => {
    localStorage.clear();
    sessionStorage.clear();
    message.success('Logged out successfully');
    window.location.href = '/login';
  }, []);

  React.useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;
    const resetTimer = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        message.warning('Tự động đăng xuất do không có thao tác trong 15 phút', 5);
        handleLogout();
      }, 15 * 60 * 1000); // 15 minutes
    };

    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
    events.forEach(event => document.addEventListener(event, resetTimer));
    resetTimer();

    return () => {
      clearTimeout(timeoutId);
      events.forEach(event => document.removeEventListener(event, resetTimer));
    };
  }, [handleLogout]);

  const currentUsername = localStorage.getItem('username') || 'User';
  const userInitial = currentUsername.charAt(0).toUpperCase();

  React.useEffect(() => {
    if (!settings) {
      api.get('/tenant/settings', { headers: { 'X-Silent-Error': 'true' } }).then(response => {
        if (response.data.success) {
          setSettings(response.data.data);
        }
      }).catch(err => console.error('Failed to load settings in background', err));
    }
  }, [settings, setSettings]);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-neutral-50 font-sans">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200 h-14 flex justify-between items-center z-50 shadow-sm shrink-0 w-full relative">
        <div className="flex items-center h-full">
          {/* Hamburger perfectly aligned with collapsed sidebar */}
          <div className="w-16 h-full flex items-center justify-center shrink-0 border-r border-transparent">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="w-8 h-8 rounded hover:bg-neutral-100 flex items-center justify-center text-neutral-500 transition-colors"
            >
              <i className="ph ph-list text-xl"></i>
            </button>
          </div>
          <div className="flex items-center gap-2 pl-2">
            {settings?.logoUrl ? (
              <img src={settings.logoUrl} alt="Logo" className="h-8 w-auto max-w-[120px] rounded object-contain" />
            ) : (
              <div className="w-8 h-8 bg-primary text-white rounded flex items-center justify-center font-bold text-lg">
                <i className="ph-fill ph-hexagon"></i>
              </div>
            )}
            <h1 className="font-bold text-neutral-800 text-lg tracking-tight truncate max-w-[200px] m-0">
              {settings?.name || 'EAM System'}
            </h1>
            <span className="ml-2 px-2 py-0.5 bg-primary-50 text-primary-600 text-xs font-semibold rounded-full hidden sm:block whitespace-nowrap">
              Admin Portal
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4 pr-6 shrink-0 h-full">
          <button className="w-8 h-8 rounded-full hover:bg-neutral-100 flex items-center justify-center text-neutral-600 transition-colors relative">
            <i className="ph ph-bell text-lg"></i>
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-danger text-white text-[9px] font-bold rounded-full flex items-center justify-center">5</span>
          </button>

          <Dropdown menu={{
            items: [
              { key: 'change-password', label: 'Change Password', icon: <SettingOutlined />, onClick: () => setChangePasswordVisible(true) },
              { type: 'divider' },
              { key: 'logout', label: <span className="text-danger">Logout</span>, onClick: handleLogout }
            ]
          }} trigger={['click']} placement="bottomRight">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary-400 to-primary-600 text-white flex items-center justify-center font-bold shadow-sm text-sm cursor-pointer hover:opacity-90 transition-opacity">
              {userInitial}
            </div>
          </Dropdown>
        </div>
      </header>

      <Modal
        title="Change Password"
        open={changePasswordVisible}
        onCancel={() => {
          setChangePasswordVisible(false);
          passwordForm.resetFields();
        }}
        onOk={() => passwordForm.submit()}
        destroyOnHidden={true}
      >
        <Form
          form={passwordForm}
          layout="vertical"
          onFinish={async (values) => {
            try {
              await api.post('/auth/change-password', values);
              message.success('Password changed successfully');
              setChangePasswordVisible(false);
              passwordForm.resetFields();
            } catch (err: any) {
              message.error(err.response?.data?.error || 'Failed to change password');
            }
          }}
        >
          <Form.Item name="oldPassword" label="Current Password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="newPassword" label="New Password" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden relative flex">
        {/* Sidebar */}
        <nav className={`${sidebarOpen ? 'w-64' : 'w-16'} bg-white border-r border-neutral-200 flex flex-col transition-all duration-300 z-40 shrink-0 shadow-[4px_0_24px_rgba(0,0,0,0.02)] overflow-hidden relative`}>

          {/* Scrollable Menu Area */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden pb-4 scrollbar-hide">
            {/* Workspace */}
            <div className="px-4 pt-4 pb-2">
              <p className={`text-[10px] font-bold text-neutral-400 uppercase tracking-[0.18em] mb-2 whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>WORKSPACE</p>
            </div>
            <div className="flex flex-col gap-0.5 px-3">
              <Link
                to="/dashboard"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/dashboard') ? 'bg-primary-50 text-primary font-semibold' : 'text-neutral-600 hover:bg-neutral-100'}`}
              >
                <i className={`${location.pathname.startsWith('/dashboard') ? 'ph-fill' : 'ph'} ph-squares-four text-lg shrink-0 ${location.pathname.startsWith('/dashboard') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/dashboard') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Dashboard</span>
              </Link>
              <Link
                to="/assets"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/assets') ? 'bg-primary-50 text-primary font-semibold' : 'text-neutral-600 hover:bg-neutral-100'}`}
              >
                <i className={`${location.pathname.startsWith('/assets') ? 'ph-fill' : 'ph'} ph-cube text-lg shrink-0 ${location.pathname.startsWith('/assets') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/assets') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Asset Registry</span>
              </Link>
              <Link
                to="/work-orders"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/work-orders') ? 'bg-primary-50 text-primary font-semibold' : 'text-neutral-600 hover:bg-neutral-100'}`}
              >
                <i className={`${location.pathname.startsWith('/work-orders') ? 'ph-fill' : 'ph'} ph-clipboard-text text-lg shrink-0 ${location.pathname.startsWith('/work-orders') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/work-orders') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Work Orders</span>
                {sidebarOpen && <span className="ml-auto bg-danger text-white text-[10px] px-1.5 py-0.5 rounded-md font-bold whitespace-nowrap">12</span>}
              </Link>
              <Link
                to="/maintenance"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/maintenance') ? 'bg-primary-50 text-primary font-semibold' : 'text-neutral-600 hover:bg-neutral-100'}`}
              >
                <i className={`${location.pathname.startsWith('/maintenance') ? 'ph-fill' : 'ph'} ph-calendar-check text-lg shrink-0 ${location.pathname.startsWith('/maintenance') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/maintenance') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Maintenance</span>
              </Link>
              <Link
                to="/reports"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/reports') ? 'bg-primary-50 text-primary font-semibold' : 'text-neutral-600 hover:bg-neutral-100'}`}
              >
                <i className={`${location.pathname.startsWith('/reports') ? 'ph-fill' : 'ph'} ph-chart-line-up text-lg shrink-0 ${location.pathname.startsWith('/reports') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/reports') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Reports</span>
              </Link>
              <Link
                to="/inventory"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/inventory') ? 'bg-primary-50 text-primary font-semibold' : 'text-neutral-600 hover:bg-neutral-100'}`}
              >
                <i className={`${location.pathname.startsWith('/inventory') ? 'ph-fill' : 'ph'} ph-package text-lg shrink-0 ${location.pathname.startsWith('/inventory') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/inventory') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Inventory</span>
              </Link>
            </div>

            {/* Admin section */}
            <div className="px-4 pt-6 pb-2">
              <p className={`text-[10px] font-bold text-neutral-400 uppercase tracking-[0.18em] mb-2 whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>ADMIN</p>
            </div>
            <div className="flex flex-col gap-0.5 px-3">
              <Link
                to="/users"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/users')
                  ? 'bg-primary-50 text-primary font-semibold'
                  : 'text-neutral-600 hover:bg-neutral-100'
                  }`}
              >
                <i className={`${location.pathname.startsWith('/users') ? 'ph-fill' : 'ph'} ph-users text-lg shrink-0 ${location.pathname.startsWith('/users') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/users') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Users</span>
              </Link>
              <Link
                to="/roles"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/roles')
                  ? 'bg-primary-50 text-primary font-semibold'
                  : 'text-neutral-600 hover:bg-neutral-100'
                  }`}
              >
                <i className={`${location.pathname.startsWith('/roles') ? 'ph-fill' : 'ph'} ph-shield-check text-lg shrink-0 ${location.pathname.startsWith('/roles') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/roles') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Roles</span>
              </Link>
              <Link
                to="/asset-categories"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/asset-categories')
                  ? 'bg-primary-50 text-primary font-semibold'
                  : 'text-neutral-600 hover:bg-neutral-100'
                  }`}
              >
                <i className={`${location.pathname.startsWith('/asset-categories') ? 'ph-fill' : 'ph'} ph-tag text-lg shrink-0 ${location.pathname.startsWith('/asset-categories') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/asset-categories') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Asset Config</span>
              </Link>
              <Link
                to="/settings"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/settings')
                  ? 'bg-primary-50 text-primary font-semibold'
                  : 'text-neutral-600 hover:bg-neutral-100'
                  }`}
              >
                <i className={`${location.pathname.startsWith('/settings') ? 'ph-fill' : 'ph'} ph-gear text-lg shrink-0 ${location.pathname.startsWith('/settings') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/settings') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Settings</span>
              </Link>
              <Link
                to="/audit"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/audit')
                  ? 'bg-primary-50 text-primary font-semibold'
                  : 'text-neutral-600 hover:bg-neutral-100'
                  }`}
              >
                <i className={`${location.pathname.startsWith('/audit') ? 'ph-fill' : 'ph'} ph-file-text text-lg shrink-0 ${location.pathname.startsWith('/audit') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                <span className={`${location.pathname.startsWith('/audit') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Audit Logs</span>
              </Link>
              {localStorage.getItem('tenantId') === '00000000-0000-0000-0000-000000000000' && (
                <Link
                  to="/system-tenants"
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group h-10 overflow-hidden ${location.pathname.startsWith('/system-tenants')
                    ? 'bg-primary-50 text-primary font-semibold'
                    : 'text-neutral-600 hover:bg-neutral-100'
                    }`}
                >
                  <i className={`${location.pathname.startsWith('/system-tenants') ? 'ph-fill' : 'ph'} ph-buildings text-lg shrink-0 ${location.pathname.startsWith('/system-tenants') ? '' : 'group-hover:text-primary transition-colors'}`}></i>
                  <span className={`${location.pathname.startsWith('/system-tenants') ? '' : 'font-medium'} text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Tenants (Super Admin)</span>
                </Link>
              )}
            </div>
          </div>

          {/* User card (CRM-style) */}
          <div className={`mt-auto p-3 overflow-hidden transition-opacity duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
            <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-3 flex items-center gap-3 w-56">
              <div className="w-9 h-9 rounded-full bg-primary text-white flex items-center justify-center font-bold text-sm shrink-0">{userInitial}</div>
              <div className="flex-1 overflow-hidden">
                <p className="text-sm font-bold text-neutral-900 truncate leading-tight">{currentUsername}</p>
                <p className="text-[11px] text-neutral-500 truncate">System User</p>
              </div>
              <button
                onClick={handleLogout}
                className="text-neutral-400 hover:text-danger hover:bg-red-50 p-1.5 rounded-md shrink-0 transition-all flex items-center justify-center"
                title="Đăng xuất"
                aria-label="Đăng xuất"
              >
                <i className="ph ph-sign-out text-lg"></i>
              </button>
            </div>
          </div>
        </nav>

        {/* Content Router */}
        <div className="flex-1 flex flex-col min-w-0 bg-neutral-50 overflow-y-auto relative">

          {/* Topbar (CRM-style: search + actions + notifications) */}
          <header className="h-16 bg-white/80 backdrop-blur-md border-b border-neutral-200 flex items-center justify-between px-6 shrink-0 z-40 sticky top-0">
            {/* Breadcrumbs Placeholder */}
            <div className="flex items-center text-xs text-neutral-500 font-semibold overflow-hidden whitespace-nowrap shrink">
              <span className="hover:text-primary cursor-pointer transition-colors flex items-center gap-1"><i className="ph ph-house text-sm"></i> Workspace</span>
              <i className="ph ph-caret-right text-[10px] mx-2 text-neutral-300"></i>
              <span className="text-neutral-900 font-bold capitalize">{location.pathname.split('/')[1] || 'Dashboard'}</span>
            </div>

            <div className="flex items-center gap-3 shrink-0 pl-4">
              {/* Search */}
              <div className="relative hidden md:block">
                <i className="ph ph-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 text-base"></i>
                <input type="text" placeholder="Search resources..." className="w-72 pl-9 pr-3 py-2 bg-neutral-50 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-primary focus:bg-white focus:ring-2 focus:ring-primary/10 transition-all" />
              </div>
            </div>
          </header>

          <div className="p-6 flex-1 flex flex-col">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/settings" element={<OrganizationSettings />} />
              <Route path="/roles" element={<RoleManagement />} />
              <Route path="/users" element={<UserManagement />} />
              <Route path="/audit" element={<AuditLogViewer />} />
              <Route path="/system-tenants" element={<SystemTenants />} />
              <Route path="/asset-categories" element={<AssetCategoryManagement />} />
              {/* Placeholder Routes */}
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/assets" element={<AssetRegistry />} />
              <Route path="/work-orders" element={<WorkOrders />} />
              <Route path="/maintenance" element={<Maintenance />} />
              <Route path="/inventory" element={<SparePartsManagement />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </div>
        </div>
      </main>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<AppShell />} />
      </Routes>
    </Router>
  );
};

export default App;
