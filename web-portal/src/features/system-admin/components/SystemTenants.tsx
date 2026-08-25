import React, { useState, useEffect } from 'react';
import { Table, Button, Space, Modal, Form, Input, Select, message, Tag, Drawer, Tooltip } from 'antd';
import { PlusOutlined, UserAddOutlined, TeamOutlined, EditOutlined, StopOutlined, CheckCircleOutlined, ExclamationCircleFilled } from '@ant-design/icons';
import api from '../../../utils/axios';

interface Tenant {
  id: string;
  name: string;
  tenantCode: string;
  servicePlan: string;
  status: string;
  createdAt: string;
}

export const SystemTenants: React.FC = () => {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [isTenantModalVisible, setIsTenantModalVisible] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [isEditTenantModalVisible, setIsEditTenantModalVisible] = useState(false);
  const [isAdminModalVisible, setIsAdminModalVisible] = useState(false);
  const [isEditAdminModalVisible, setIsEditAdminModalVisible] = useState(false);
  const [isViewAdminsVisible, setIsViewAdminsVisible] = useState(false);
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);
  const [selectedAdminId, setSelectedAdminId] = useState<string | null>(null);
  const [tenantAdmins, setTenantAdmins] = useState<any[]>([]);
  
  const [tenantForm] = Form.useForm();
  const [editTenantForm] = Form.useForm();
  const [adminForm] = Form.useForm();
  const [editAdminForm] = Form.useForm();

  const fetchTenants = async () => {
    setLoading(true);
    try {
      const response = await api.get('/system/tenants');
      setTenants(response.data.data || []);
    } catch (error: any) {
      if (error?.response?.status === 403 || error?.response?.status === 401) {
        // Interceptor handles this
        console.log("Ignored 403/401 error in fetchTenants");
      } else {
        message.error('Failed to fetch tenants');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const handleCreateTenant = async (values: any) => {
    setSubmitting(true);
    try {
      await api.post('/system/tenants', values);
      message.success('Tenant created successfully');
      setIsTenantModalVisible(false);
      tenantForm.resetFields();
      fetchTenants();
    } catch (error) {
      message.error('Failed to create tenant');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditTenant = async (values: any) => {
    if (!selectedTenantId) return;
    setSubmitting(true);
    try {
      await api.put(`/system/tenants/${selectedTenantId}`, values);
      message.success('Tenant updated successfully');
      setIsEditTenantModalVisible(false);
      fetchTenants();
    } catch (error) {
      message.error('Failed to update tenant');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleTenantStatus = (tenantId: string, currentStatus: string) => {
    const isBlocking = currentStatus === 'ACTIVE';
    Modal.confirm({
      title: isBlocking ? 'Are you sure you want to block this tenant?' : 'Are you sure you want to unblock this tenant?',
      icon: isBlocking ? <ExclamationCircleFilled /> : <ExclamationCircleFilled style={{ color: '#52c41a' }} />,
      content: isBlocking ? 'All users in this tenant will lose access.' : 'This tenant and its users will regain access to the system.',
      okText: isBlocking ? 'Yes, block tenant' : 'Yes, unblock tenant',
      okType: isBlocking ? 'danger' : 'primary',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          const newStatus = isBlocking ? 'INACTIVE' : 'ACTIVE';
          await api.put(`/system/tenants/${tenantId}/status`, { status: newStatus });
          message.success(`Tenant ${newStatus.toLowerCase()} successfully`);
          fetchTenants();
        } catch (error) {
          message.error('Failed to toggle tenant status');
        }
      }
    });
  };

  const handleCreateAdmin = async (values: any) => {
    if (!selectedTenantId) return;
    setSubmitting(true);
    try {
      await api.post(`/system/tenants/${selectedTenantId}/admins`, values);
      message.success('Tenant admin created successfully');
      setIsAdminModalVisible(false);
      adminForm.resetFields();
      fetchTenantAdmins(selectedTenantId);
    } catch (error) {
      message.error('Failed to create tenant admin');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditAdmin = async (values: any) => {
    if (!selectedTenantId || !selectedAdminId) return;
    setSubmitting(true);
    try {
      await api.put(`/system/tenants/${selectedTenantId}/admins/${selectedAdminId}`, values);
      message.success('Admin updated successfully');
      setIsEditAdminModalVisible(false);
      fetchTenantAdmins(selectedTenantId);
    } catch (error) {
      message.error('Failed to update admin');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleAdminStatus = (adminId: string, currentStatus: string) => {
    if (!selectedTenantId) return;
    const isBlocking = currentStatus === 'ACTIVE';
    Modal.confirm({
      title: isBlocking ? 'Are you sure you want to block this admin?' : 'Are you sure you want to unblock this admin?',
      icon: isBlocking ? <ExclamationCircleFilled /> : <ExclamationCircleFilled style={{ color: '#52c41a' }} />,
      content: isBlocking ? 'This admin will no longer be able to log in.' : 'This admin will regain access to the system.',
      okText: isBlocking ? 'Yes, block admin' : 'Yes, unblock admin',
      okType: isBlocking ? 'danger' : 'primary',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          const newStatus = isBlocking ? 'INACTIVE' : 'ACTIVE';
          await api.put(`/system/tenants/${selectedTenantId}/admins/${adminId}/status`, { status: newStatus });
          message.success(`Admin ${newStatus.toLowerCase()} successfully`);
          fetchTenantAdmins(selectedTenantId);
        } catch (error) {
          message.error('Failed to toggle admin status');
        }
      }
    });
  };

  const fetchTenantAdmins = async (tenantId: string) => {
    try {
      const response = await api.get(`/system/tenants/${tenantId}/admins`);
      setTenantAdmins(response.data.data || []);
    } catch (error: any) {
      if (error?.response?.status === 403 || error?.response?.status === 401) {
        // Interceptor handles this
        console.log("Ignored 403/401 error in fetchTenantAdmins");
      } else {
        message.error('Failed to fetch tenant admins');
      }
    }
  };

  const openViewAdmins = (tenantId: string) => {
    setSelectedTenantId(tenantId);
    fetchTenantAdmins(tenantId);
    setIsViewAdminsVisible(true);
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: Tenant, b: Tenant) => a.name.localeCompare(b.name),
    },
    {
      title: 'Tenant Code',
      dataIndex: 'tenantCode',
      key: 'tenantCode',
      sorter: (a: Tenant, b: Tenant) => a.tenantCode.localeCompare(b.tenantCode),
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: 'Service Plan',
      dataIndex: 'servicePlan',
      key: 'servicePlan',
      sorter: (a: Tenant, b: Tenant) => a.servicePlan.localeCompare(b.servicePlan),
      filters: [
        { text: 'FREE', value: 'FREE' },
        { text: 'PRO', value: 'PRO' },
        { text: 'ENTERPRISE', value: 'ENTERPRISE' },
      ],
      onFilter: (value: any, record: Tenant) => record.servicePlan === value,
      render: (text: string) => <Tag color="green">{text}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      sorter: (a: Tenant, b: Tenant) => (a.status || 'ACTIVE').localeCompare(b.status || 'ACTIVE'),
      filters: [
        { text: 'ACTIVE', value: 'ACTIVE' },
        { text: 'INACTIVE', value: 'INACTIVE' },
      ],
      onFilter: (value: any, record: Tenant) => (record.status || 'ACTIVE') === value,
      render: (status: string) => <Tag color={status === 'ACTIVE' ? 'green' : 'red'}>{status || 'ACTIVE'}</Tag>
    },
    {
      title: 'Created At',
      dataIndex: 'createdAt',
      key: 'createdAt',
      sorter: (a: Tenant, b: Tenant) => new Date(a.createdAt || 0).getTime() - new Date(b.createdAt || 0).getTime(),
      render: (text: string) => text ? new Date(text).toLocaleString() : 'N/A',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Tenant) => (
        <Space size="middle">
          <Tooltip title="Create Admin">
            <Button 
              type="text" 
              icon={<UserAddOutlined />} 
              onClick={() => {
                setSelectedTenantId(record.id);
                setIsAdminModalVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="View Admins">
            <Button 
              type="text" 
              icon={<TeamOutlined />} 
              onClick={() => openViewAdmins(record.id)}
            />
          </Tooltip>
          <Tooltip title="Edit Tenant">
            <Button 
              type="text" 
              icon={<EditOutlined />} 
              onClick={() => {
                setSelectedTenantId(record.id);
                editTenantForm.setFieldsValue({
                  name: record.name,
                  servicePlan: record.servicePlan,
                });
                setIsEditTenantModalVisible(true);
              }}
            />
          </Tooltip>
          {record.id !== '00000000-0000-0000-0000-000000000000' && (
            <Tooltip title={record.status === 'ACTIVE' ? 'Block' : 'Unblock'}>
              <Button 
                type="text" 
                danger={record.status === 'ACTIVE'}
                style={{ color: record.status !== 'ACTIVE' ? '#52c41a' : undefined }}
                icon={record.status === 'ACTIVE' ? <StopOutlined /> : <CheckCircleOutlined />} 
                onClick={() => handleToggleTenantStatus(record.id, record.status || 'ACTIVE')}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  const adminColumns = [
    {
      title: 'Username/Email',
      dataIndex: 'username',
      key: 'username',
      sorter: (a: any, b: any) => (a.username || '').localeCompare(b.username || ''),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      sorter: (a: any, b: any) => (a.status || '').localeCompare(b.status || ''),
      filters: [
        { text: 'ACTIVE', value: 'ACTIVE' },
        { text: 'INACTIVE', value: 'INACTIVE' },
      ],
      onFilter: (value: any, record: any) => record.status === value,
      render: (status: string) => <Tag color={status === 'ACTIVE' ? 'green' : 'red'}>{status}</Tag>
    },
    {
      title: 'Created At',
      dataIndex: 'createdAt',
      key: 'createdAt',
      sorter: (a: any, b: any) => new Date(a.createdAt || 0).getTime() - new Date(b.createdAt || 0).getTime(),
      render: (text: string) => text ? new Date(text).toLocaleString() : 'N/A',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: any) => (
        <Space size="middle">
          <Tooltip title="Edit Admin">
            <Button 
              type="text" 
              icon={<EditOutlined />} 
              onClick={() => {
                setSelectedAdminId(record.id);
                editAdminForm.setFieldsValue({
                  username: record.username,
                });
                setIsEditAdminModalVisible(true);
              }}
            />
          </Tooltip>
          {record.id !== '00000000-0000-0000-0000-000000000000' && (
            <Tooltip title={record.status === 'ACTIVE' ? 'Block' : 'Unblock'}>
              <Button 
                type="text" 
                danger={record.status === 'ACTIVE'}
                style={{ color: record.status !== 'ACTIVE' ? '#52c41a' : undefined }}
                icon={record.status === 'ACTIVE' ? <StopOutlined /> : <CheckCircleOutlined />} 
                onClick={() => handleToggleAdminStatus(record.id, record.status)}
              />
            </Tooltip>
          )}
        </Space>
      )
    }
  ];

  const totalTenants = tenants.length;
  const activeTenants = tenants.filter(t => t.status === 'ACTIVE').length;
  const enterpriseTenants = tenants.filter(t => t.servicePlan === 'ENTERPRISE').length;
  const proTenants = tenants.filter(t => t.servicePlan === 'PRO').length;

  return (
    <div className="bg-transparent h-full flex flex-col space-y-6">
      {/* Massive Beautiful Header */}
      <div className="bg-white p-6 md:p-8 rounded-3xl border border-neutral-200/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative overflow-hidden shrink-0 group">
        <div className="absolute top-0 right-0 -mr-32 -mt-32 w-[500px] h-[500px] rounded-full bg-gradient-to-bl from-primary-200/40 via-primary-50/20 to-transparent blur-3xl opacity-60 pointer-events-none group-hover:scale-110 transition-transform duration-1000"></div>
        <div className="absolute bottom-0 left-0 -ml-32 -mb-32 w-80 h-80 rounded-full bg-gradient-to-tr from-info/10 to-transparent blur-3xl opacity-50 pointer-events-none"></div>
        
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center text-primary shadow-[inset_0_2px_10px_rgba(255,255,255,1),0_4px_15px_rgba(0,160,226,0.2)] border border-primary/20 transform -rotate-12 group-hover:rotate-12 group-hover:scale-110 transition duration-500">
              <i className="ph-fill ph-buildings text-3xl drop-shadow-sm"></i>
            </div>
            <div>
              <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-neutral-900 via-neutral-700 to-neutral-600 tracking-tight m-0 drop-shadow-sm">
                System Tenants
              </h2>
              <p className="text-neutral-500 text-base font-medium mt-1 mb-0 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-success animate-pulse"></span>
                Manage organizations, plans, and multi-tenant isolation.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button 
              type="primary" 
              icon={<PlusOutlined className="text-lg" />} 
              onClick={() => setIsTenantModalVisible(true)}
              className="rounded-xl h-11 px-8 bg-gradient-to-r from-primary to-primary-600 hover:from-primary-500 hover:to-primary-700 shadow-[0_8px_20px_rgba(0,160,226,0.3)] border-0 transition transform hover:-translate-y-1 transform-gpu hover:scale-105 font-bold text-white flex items-center justify-center gap-2"
            >
              New Tenant
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 shrink-0">
        <div className="bg-white  rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary-50/50 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Total Tenants</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{totalTenants}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-primary-50 text-primary flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-buildings text-xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-white  rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-success/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Active</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{activeTenants}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-success/10 text-success flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-check-circle text-xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-white  rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-warning/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Enterprise</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{enterpriseTenants}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-warning/10 text-warning flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-crown text-xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-white  rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-info/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Pro Plan</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{proTenants}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-info/10 text-info flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-rocket text-xl"></i>
            </div>
          </div>
        </div>
      </div>

      {/* Main Table Container */}
      <div className="bg-white rounded-3xl border border-neutral-200/60 shadow-[0_8px_30px_rgb(0,0,0,0.03)] flex-1 flex flex-col overflow-hidden relative">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary-300 via-primary-500 to-primary-600"></div>
        
        {/* Search Bar */}
        <div className="p-4 md:p-5 border-b border-neutral-100/80 bg-white/40 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-4 shrink-0 relative z-10">
          <Input 
            prefix={<i className="ph-bold ph-magnifying-glass text-neutral-400 mr-2 text-lg"></i>}
            placeholder="Search tenants by name..." 
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full sm:max-w-md h-12 rounded-xl border-neutral-200/80 hover:border-primary focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(0,160,226,0.15)] bg-neutral-50/50 hover:bg-white focus-within:bg-white transition-all text-base font-medium px-4 shadow-[0_2px_10px_rgba(0,0,0,0.02)]"
          />
          <div className="flex items-center gap-2 text-sm font-bold text-neutral-500 bg-neutral-50/80 px-4 py-2 rounded-lg border border-neutral-100">
             <i className="ph-fill ph-buildings text-primary"></i>
             <span>
                {tenants.filter(t => (t.name || '').toLowerCase().includes(searchText.toLowerCase())).length} Tenants Found
             </span>
          </div>
        </div>

        <div className="p-2 flex-1 flex flex-col">
          <Table 
            columns={columns} 
            dataSource={tenants.filter(t => (t.name || '').toLowerCase().includes(searchText.toLowerCase()))} 
            rowKey="id" 
            loading={loading}
            size="middle"
            className="flex-1 custom-beautiful-table"
            onChange={(pagination) => sessionStorage.setItem('SystemTenants_page', pagination.current?.toString() || '1')}
            pagination={{ pageSize: 10, defaultCurrent: parseInt(sessionStorage.getItem('SystemTenants_page') || '1', 10), className: 'mt-6 px-4 pb-4' }}
            scroll={{ x: 'max-content' }}
          />
        </div>
      </div>

      <Modal
        title="Create New Tenant"
        open={isTenantModalVisible}
        onCancel={() => setIsTenantModalVisible(false)}
        onOk={() => tenantForm.submit()}
        confirmLoading={submitting}
        okButtonProps={{ disabled: submitting }}
        cancelButtonProps={{ disabled: submitting }}
      >
        <Form form={tenantForm} layout="vertical" onFinish={handleCreateTenant}>
          <Form.Item name="name" label="Tenant Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="tenantCode" label="Tenant Code" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="servicePlan" label="Service Plan" initialValue="FREE">
            <Select>
              <Select.Option value="FREE">Free</Select.Option>
              <Select.Option value="PRO">Pro</Select.Option>
              <Select.Option value="ENTERPRISE">Enterprise</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Edit Tenant"
        open={isEditTenantModalVisible}
        onCancel={() => setIsEditTenantModalVisible(false)}
        onOk={() => editTenantForm.submit()}
        confirmLoading={submitting}
        okButtonProps={{ disabled: submitting }}
        cancelButtonProps={{ disabled: submitting }}
      >
        <Form form={editTenantForm} layout="vertical" onFinish={handleEditTenant}>
          <Form.Item name="name" label="Tenant Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="servicePlan" label="Service Plan" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="FREE">Free</Select.Option>
              <Select.Option value="PRO">Pro</Select.Option>
              <Select.Option value="ENTERPRISE">Enterprise</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Create Tenant Admin"
        open={isAdminModalVisible}
        onCancel={() => setIsAdminModalVisible(false)}
        onOk={() => adminForm.submit()}
        confirmLoading={submitting}
        okButtonProps={{ disabled: submitting }}
        cancelButtonProps={{ disabled: submitting }}
      >
        <Form form={adminForm} layout="vertical" onFinish={handleCreateAdmin}>
          <Form.Item name="username" label="Admin Email (Username)" rules={[{ required: true, type: 'email' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="Temporary Password" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Edit Admin"
        open={isEditAdminModalVisible}
        onCancel={() => setIsEditAdminModalVisible(false)}
        onOk={() => editAdminForm.submit()}
        confirmLoading={submitting}
        okButtonProps={{ disabled: submitting }}
        cancelButtonProps={{ disabled: submitting }}
      >
        <Form form={editAdminForm} layout="vertical" onFinish={handleEditAdmin}>
          <Form.Item name="username" label="Admin Email (Username)" rules={[{ required: true, type: 'email' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="New Password (leave blank to keep current)">
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title="Tenant Admins"
        placement="right"
        size="large"
        onClose={() => setIsViewAdminsVisible(false)}
        open={isViewAdminsVisible}
      >
        <Table 
          dataSource={tenantAdmins} 
          rowKey="id"
          columns={adminColumns}
          onChange={(pagination) => sessionStorage.setItem('SystemTenantsAdmin_page', pagination.current?.toString() || '1')}
          pagination={{ defaultCurrent: parseInt(sessionStorage.getItem('SystemTenantsAdmin_page') || '1', 10) }}
        />
      </Drawer>
    </div>
  );
};
