import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Checkbox, message, Space, Popconfirm, Tag, Select } from 'antd';
import { EditOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import api from '../../../utils/axios';

interface Permission {
  id: string;
  name: string;
  description: string;
}

interface Role {
  id: string;
  name: string;
  description: string;
  isSystem: boolean;
  permissions: Permission[];
}

export const RoleManagement: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [deleteRoleModalVisible, setDeleteRoleModalVisible] = useState(false);
  const [roleToDelete, setRoleToDelete] = useState<Role | null>(null);
  const [fallbackRoleId, setFallbackRoleId] = useState<string>('');
  const [form] = Form.useForm();

  const fetchRoles = async () => {
    setLoading(true);
    try {
      const response = await api.get('/roles');
      if (response.data.success) {
        setRoles(response.data.data);
      }
    } catch (error) {
      console.error('Failed to fetch roles:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPermissions = async () => {
    try {
      const response = await api.get('/permissions');
      if (response.data.success) {
        setPermissions(response.data.data);
      }
    } catch (error) {
      console.error('Failed to fetch permissions:', error);
    }
  };

  useEffect(() => {
    fetchRoles();
    fetchPermissions();
  }, []);

  const handleAdd = () => {
    setEditingRole(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleEdit = (role: Role) => {
    setEditingRole(role);
    form.setFieldsValue({
      name: role.name,
      description: role.description,
      permissionIds: role.permissions.map(p => p.id),
    });
    setIsModalVisible(true);
  };

  const handleDelete = async (id: string, fallbackId?: string) => {
    try {
      const url = fallbackId ? `/roles/${id}?fallbackRoleId=${fallbackId}` : `/roles/${id}`;
      const response = await api.delete(url);
      if (response.data.success) {
        message.success('Role deleted successfully');
        setDeleteRoleModalVisible(false);
        fetchRoles();
      }
    } catch (error: any) {
      if (error.response?.data?.message === 'ROLE_HAS_USERS') {
        setRoleToDelete(roles.find(r => r.id === id) || null);
        setFallbackRoleId('');
        setDeleteRoleModalVisible(true);
      } else {
        message.error(error.response?.data?.message || 'Failed to delete role');
      }
    }
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      
      if (editingRole) {
        const response = await api.put(`/roles/${editingRole.id}`, values);
        if (response.data.success) {
          message.success('Role updated successfully');
        }
      } else {
        const response = await api.post('/roles', values);
        if (response.data.success) {
          message.success('Role created successfully');
        }
      }
      setIsModalVisible(false);
      fetchRoles();
    } catch (error) {
      console.error('Form validation failed:', error);
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: Role, b: Role) => a.name.localeCompare(b.name),
      render: (text: string, record: Role) => (
        <Space>
          <span className="font-semibold text-neutral-800">{text}</span>
          {record.isSystem && <Tag color="blue">System</Tag>}
        </Space>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      sorter: (a: Role, b: Role) => (a.description || '').localeCompare(b.description || ''),
    },
    {
      title: 'Permissions',
      key: 'permissions',
      render: (_: any, record: Role) => (
        <div className="flex flex-wrap gap-1 max-w-[300px]">
          {record.permissions.map(p => (
            <Tag key={p.id} color="cyan">{p.name}</Tag>
          ))}
        </div>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_: any, record: Role) => (
        <Space size="middle">
          <Button 
            type="text" 
            icon={<EditOutlined />} 
            onClick={() => handleEdit(record)}
            disabled={record.isSystem}
          />
          <Popconfirm
            title="Are you sure you want to delete this role?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
            disabled={record.isSystem}
          >
            <Button 
              type="text" 
              danger 
              icon={<DeleteOutlined />} 
              disabled={record.isSystem}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const totalRoles = roles.length;
  const systemRoles = roles.filter(r => r.isSystem).length;
  const customRoles = totalRoles - systemRoles;

  return (
    <div className="bg-transparent h-full flex flex-col space-y-6">
      {/* Massive Beautiful Header */}
      <div className="bg-white backdrop-blur-2xl p-6 md:p-8 rounded-3xl border border-neutral-200/80 shadow-[0_8px_30px_rgb(0,0,0,0.06)] relative overflow-hidden shrink-0 group">
        <div className="absolute top-0 right-0 -mr-32 -mt-32 w-[600px] h-[600px] rounded-full bg-gradient-to-bl from-info/20 via-primary-100/30 to-transparent blur-3xl opacity-70 pointer-events-none group-hover:scale-105 transition-transform duration-1000"></div>
        <div className="absolute bottom-0 left-0 -ml-40 -mb-40 w-96 h-96 rounded-full bg-gradient-to-tr from-primary-200/20 to-transparent blur-3xl opacity-60 pointer-events-none"></div>
        
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-info/10 to-info/20 flex items-center justify-center text-info shadow-[inset_0_2px_10px_rgba(255,255,255,1),0_4px_15px_rgba(22,119,255,0.2)] border border-info/20 transform rotate-12 group-hover:-rotate-12 group-hover:scale-110 transition duration-500">
              <i className="ph-fill ph-shield-check text-3xl drop-shadow-sm"></i>
            </div>
            <div>
              <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-neutral-900 via-neutral-800 to-neutral-700 tracking-tight m-0 drop-shadow-sm">
                Role Management
              </h2>
              <p className="text-neutral-500 text-base font-medium mt-1 mb-0 flex items-center gap-2">
                <i className="ph-fill ph-lock-key text-neutral-400"></i>
                Define and manage security roles and permissions.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button 
              type="primary" 
              icon={<PlusOutlined className="text-lg" />} 
              onClick={handleAdd} 
              className="rounded-xl h-11 px-8 bg-gradient-to-r from-primary to-primary-600 hover:from-primary-500 hover:to-primary-700 shadow-[0_8px_20px_rgba(0,160,226,0.35)] border-0 transition transform hover:-translate-y-1 transform-gpu hover:scale-105 font-bold text-white flex items-center justify-center gap-2 text-base"
            >
              Create Role
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6 shrink-0">
        <div className="bg-gradient-to-br from-white to-neutral-50/80  rounded-2xl p-6 border border-neutral-200/80 shadow-sm hover:shadow-lg transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-center relative z-10">
            <div>
              <p className="text-sm font-extrabold text-neutral-400 uppercase tracking-widest mb-2">Total Roles</p>
              <h3 className="text-4xl font-black text-neutral-900 m-0">{totalRoles}</h3>
            </div>
            <div className="w-14 h-14 rounded-full bg-white shadow-[0_4px_15px_rgba(0,0,0,0.05)] border border-neutral-100 flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
              <i className="ph-fill ph-circles-three-plus text-2xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-white to-info/5  rounded-2xl p-6 border border-info/20 shadow-sm hover:shadow-lg transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-info/10 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-center relative z-10">
            <div>
              <p className="text-sm font-extrabold text-info/70 uppercase tracking-widest mb-2">System Roles</p>
              <h3 className="text-4xl font-black text-info m-0">{systemRoles}</h3>
            </div>
            <div className="w-14 h-14 rounded-full bg-white shadow-[0_4px_15px_rgba(22,119,255,0.1)] border border-info/20 flex items-center justify-center text-info group-hover:scale-110 transition-transform">
              <i className="ph-fill ph-cpu text-2xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-white to-success/5  rounded-2xl p-6 border border-success/20 shadow-sm hover:shadow-lg transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-success/10 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-center relative z-10">
            <div>
              <p className="text-sm font-extrabold text-success/70 uppercase tracking-widest mb-2">Custom Roles</p>
              <h3 className="text-4xl font-black text-success m-0">{customRoles}</h3>
            </div>
            <div className="w-14 h-14 rounded-full bg-white shadow-[0_4px_15px_rgba(82,196,26,0.1)] border border-success/20 flex items-center justify-center text-success group-hover:scale-110 transition-transform">
              <i className="ph-fill ph-users-three text-2xl"></i>
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
            placeholder="Search roles by name or description..." 
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full sm:max-w-md h-12 rounded-xl border-neutral-200/80 hover:border-primary focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(0,160,226,0.15)] bg-neutral-50/50 hover:bg-white focus-within:bg-white transition-all text-base font-medium px-4 shadow-[0_2px_10px_rgba(0,0,0,0.02)]"
          />
          <div className="flex items-center gap-2 text-sm font-bold text-neutral-500 bg-neutral-50/80 px-4 py-2 rounded-lg border border-neutral-100">
             <i className="ph-fill ph-shield-check text-primary"></i>
             <span>
                {roles.filter(r => (r.name || '').toLowerCase().includes(searchText.toLowerCase()) || (r.description || '').toLowerCase().includes(searchText.toLowerCase())).length} Roles Found
             </span>
          </div>
        </div>

        <div className="p-3 flex-1 flex flex-col">
          <Table 
            columns={columns} 
            dataSource={roles.filter(r => 
              (r.name || '').toLowerCase().includes(searchText.toLowerCase()) || 
              (r.description || '').toLowerCase().includes(searchText.toLowerCase())
            )} 
            rowKey="id" 
            loading={loading}
            size="middle"
            className="flex-1 custom-beautiful-table"
            onChange={(pagination) => sessionStorage.setItem('RoleManagement_page', pagination.current?.toString() || '1')}
            pagination={{ pageSize: 10, defaultCurrent: parseInt(sessionStorage.getItem('RoleManagement_page') || '1', 10), className: 'mt-6 px-4 pb-4' }}
            scroll={{ x: 'max-content' }}
          />
        </div>
      </div>

      <Modal
        title={
          <div className="flex items-center gap-3 pb-3 border-b border-neutral-100">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-50 to-primary-100 border border-primary/20 flex items-center justify-center text-primary shadow-inner">
              <i className={`ph-fill ${editingRole ? 'ph-pencil-simple' : 'ph-shield-plus'} text-2xl`}></i>
            </div>
            <div>
              <h3 className="text-xl font-black text-neutral-900 m-0">{editingRole ? "Edit Role" : "Create New Role"}</h3>
              <p className="text-sm font-medium text-neutral-500 m-0 mt-0.5">{editingRole ? "Update permissions for this role." : "Define a new security role."}</p>
            </div>
          </div>
        }
        open={isModalVisible}
        onOk={handleOk}
        onCancel={() => setIsModalVisible(false)}
        width={800}
        confirmLoading={submitting}
        okButtonProps={{ 
          disabled: submitting,
          className: "bg-gradient-to-r from-primary to-primary-600 border-0 shadow-lg shadow-primary/40 h-12 px-8 font-bold text-base rounded-xl hover:scale-105 transition-transform" 
        }}
        cancelButtonProps={{ disabled: submitting, className: "h-12 px-6 font-bold text-neutral-600 rounded-xl bg-neutral-100 border-0 hover:bg-neutral-200 transition-colors" }}
        className="rounded-[24px] overflow-hidden fancy-modal"
        closeIcon={<div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-500 hover:bg-danger hover:text-white transition-colors"><i className="ph ph-x"></i></div>}
      >
        <Form form={form} layout="vertical" className="mt-6 px-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Form.Item
              name="name"
              label={<span className="font-extrabold text-neutral-700 text-sm uppercase tracking-wide">Role Name</span>}
              rules={[{ required: true, message: 'Please enter role name' }]}
            >
              <Input className="rounded-xl h-14 border-neutral-300 focus:border-primary focus:shadow-[0_0_0_3px_rgba(0,160,226,0.15)] bg-neutral-50/50 focus:bg-white transition text-base px-5 font-semibold" placeholder="e.g. Regional Manager" />
            </Form.Item>
            
            <Form.Item
              name="description"
              label={<span className="font-extrabold text-neutral-700 text-sm uppercase tracking-wide">Description</span>}
            >
              <Input className="rounded-xl h-14 border-neutral-300 focus:border-primary focus:shadow-[0_0_0_3px_rgba(0,160,226,0.15)] bg-neutral-50/50 focus:bg-white transition text-base px-5 font-medium" placeholder="Describe the purpose..." />
            </Form.Item>
          </div>

          <div className="mt-8 mb-4">
            <h4 className="font-extrabold text-neutral-900 text-lg m-0 flex items-center gap-2">
              <i className="ph-fill ph-key text-warning text-xl"></i> Permissions Assignment
            </h4>
            <p className="text-neutral-500 text-sm font-medium mt-1">Select the capabilities granted to this role.</p>
          </div>

          <Form.Item
            name="permissionIds"
            rules={[{ required: true, message: 'Please select at least one permission' }]}
            className="mb-0"
          >
            <Checkbox.Group className="w-full">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {permissions.map(p => (
                  <div key={p.id} className="relative group cursor-pointer h-full">
                    <Checkbox value={p.id} className="w-full h-full m-0">
                      <div className="border border-neutral-200/80 rounded-2xl p-4 bg-white hover:bg-primary-50/50 hover:border-primary/40 transition shadow-sm hover:shadow-md h-full flex flex-col group-hover:-translate-y-1 transform-gpu duration-300">
                        <div className="flex items-center gap-2 mb-2">
                          <div className="w-8 h-8 rounded-lg bg-neutral-100 flex items-center justify-center text-neutral-600 group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                            <i className="ph-fill ph-shield text-lg"></i>
                          </div>
                          <span className="font-bold text-neutral-800 text-sm">{p.name}</span>
                        </div>
                        <p className="text-xs text-neutral-500 m-0 mt-auto font-medium leading-relaxed">{p.description}</p>
                      </div>
                    </Checkbox>
                  </div>
                ))}
              </div>
            </Checkbox.Group>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={
          <div className="flex items-center gap-3 pb-3 border-b border-neutral-100">
            <div className="w-12 h-12 rounded-xl bg-danger/10 border border-danger/20 flex items-center justify-center text-danger">
              <i className="ph-fill ph-warning-circle text-2xl"></i>
            </div>
            <div>
              <h3 className="text-xl font-black text-neutral-900 m-0">Role is Currently Assigned</h3>
              <p className="text-sm font-medium text-neutral-500 m-0 mt-0.5">Please reassign users to continue.</p>
            </div>
          </div>
        }
        open={deleteRoleModalVisible}
        onOk={() => {
          if (!fallbackRoleId) {
            message.error('Please select a fallback role');
            return;
          }
          if (roleToDelete) handleDelete(roleToDelete.id, fallbackRoleId);
        }}
        onCancel={() => setDeleteRoleModalVisible(false)}
        okText="Reassign and Delete"
        cancelText="Cancel"
        okButtonProps={{ 
          danger: true, 
          className: "bg-danger hover:bg-danger-hover border-0 shadow-lg shadow-danger/30 h-11 px-6 font-bold text-base rounded-xl transition-transform" 
        }}
        cancelButtonProps={{ className: "h-11 px-6 font-bold text-neutral-600 rounded-xl bg-neutral-100 border-0 hover:bg-neutral-200 transition-colors" }}
        className="rounded-[24px] overflow-hidden fancy-modal"
        closeIcon={<div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-500 hover:bg-danger hover:text-white transition-colors"><i className="ph ph-x"></i></div>}
      >
        <div className="py-4">
          <div className="mb-6 p-4 bg-warning/10 rounded-xl border border-warning/20 text-neutral-700 font-medium text-[15px] leading-relaxed">
            The role <strong className="text-neutral-900">{roleToDelete?.name}</strong> is currently assigned to one or more users. 
            Please select a replacement role to assign to these users before this role can be deleted safely.
          </div>
          
          <label className="block font-extrabold text-neutral-700 text-sm uppercase tracking-wide mb-2">Replacement Role</label>
          <Select
            className="w-full h-14 custom-beautiful-select"
            placeholder="Select replacement role..."
            value={fallbackRoleId || undefined}
            onChange={setFallbackRoleId}
            options={roles.filter(r => r.id !== roleToDelete?.id).map(r => ({ label: r.name, value: r.id }))}
          />
        </div>
      </Modal>
    </div>
  );
};
