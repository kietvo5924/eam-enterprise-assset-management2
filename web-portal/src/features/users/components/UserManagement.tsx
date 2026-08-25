import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Tag, Modal, Form, Input, Select, Upload, message } from 'antd';
import * as XLSX from 'xlsx';
import { UploadOutlined, UserAddOutlined, MailOutlined, EditOutlined, StopOutlined, CheckCircleOutlined, ExclamationCircleFilled } from '@ant-design/icons';
import api from '../../../utils/axios';

interface User {
  id: string;
  username: string;
  email: string;
  status: string;
  roles: string[];
  roleIds?: string[];
}

interface Role {
  id: string;
  name: string;
}

export const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isInviteVisible, setIsInviteVisible] = useState(false);
  const [isImportVisible, setIsImportVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [searchText, setSearchText] = useState('');
  const [form] = Form.useForm();
  const [inviteForm] = Form.useForm();

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await api.get('/users?size=100');
      if (response.data.success) {
        setUsers(response.data.data.content);
      }
    } catch (error: any) {
      if (error.response?.status !== 403) {
        message.error('Failed to fetch users');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchRoles = async () => {
    try {
      const response = await api.get('/roles');
      if (response.data.success) {
        setRoles(response.data.data);
      }
    } catch (error: any) {
      if (error.response?.status !== 403) {
        message.error('Failed to fetch roles');
      }
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchRoles();
  }, []);

  const handleAddEdit = async (values: any) => {
    setSubmitting(true);
    try {
      if (editingUser) {
        await api.put(`/users/${editingUser.id}`, values);
        message.success('User updated successfully');
      } else {
        await api.post('/users', values);
        message.success('User created successfully');
      }
      setIsModalVisible(false);
      form.resetFields();
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.error || 'Failed to save user');
    } finally {
      setSubmitting(false);
    }
  };

  const handleInvite = async (values: any) => {
    setSubmitting(true);
    try {
      await api.post('/users/invite', values);
      message.success('Invitation sent successfully');
      setIsInviteVisible(false);
      inviteForm.resetFields();
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.error || 'Failed to invite user');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDisable = (id: string) => {
    Modal.confirm({
      title: 'Are you sure you want to block this user?',
      icon: <ExclamationCircleFilled />,
      content: 'This user will no longer be able to log in.',
      okText: 'Yes, block user',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await api.put(`/users/${id}/disable`);
          message.success('User disabled successfully');
          fetchUsers();
        } catch (error) {
          message.error('Failed to disable user');
        }
      }
    });
  };

  const handleEnable = (id: string) => {
    Modal.confirm({
      title: 'Are you sure you want to unblock this user?',
      icon: <ExclamationCircleFilled style={{ color: '#52c41a' }} />,
      content: 'This user will regain access to the system.',
      okText: 'Yes, unblock user',
      okType: 'primary',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await api.put(`/users/${id}/enable`);
          message.success('User enabled successfully');
          fetchUsers();
        } catch (error) {
          message.error('Failed to enable user');
        }
      }
    });
  };

  const openAddModal = () => {
    setEditingUser(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleDownloadTemplate = () => {
    const templateData = [
      { username: 'john_doe', email: 'john@company.com', password: 'Password123', role1: 'Admin', role2: 'User' },
      { username: 'jane_smith', email: 'jane@company.com', password: 'Password123', role1: 'User', role2: '' }
    ];
    const worksheet = XLSX.utils.json_to_sheet(templateData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Template");
    XLSX.writeFile(workbook, "User_Import_Template.xlsx");
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    form.setFieldsValue({ username: user.username, email: user.email, roleIds: user.roleIds });
    setIsModalVisible(true);
  };

  const columns = [
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
      sorter: (a: User, b: User) => a.username.localeCompare(b.username),
      render: (text: string) => <span className="font-semibold text-gray-800">{text}</span>
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      sorter: (a: User, b: User) => a.email.localeCompare(b.email),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      sorter: (a: User, b: User) => a.status.localeCompare(b.status),
      filters: [
        { text: 'ACTIVE', value: 'ACTIVE' },
        { text: 'INACTIVE', value: 'INACTIVE' },
        { text: 'PENDING', value: 'PENDING' },
      ],
      onFilter: (value: any, record: User) => record.status === value,
      render: (status: string) => {
        let color = status === 'ACTIVE' ? 'green' : status === 'PENDING' ? 'gold' : 'red';
        return <Tag color={color} className="rounded-full px-3">{status}</Tag>;
      },
    },
    {
      title: 'Roles',
      key: 'roles',
      dataIndex: 'roles',
      render: (roles: string[]) => (
        <Space size={[0, 4]} wrap>
          {roles?.map((role) => (
            <Tag color="blue" key={role} className="rounded-md border-blue-200">{role}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: 'Actions',
      key: 'action',
      render: (_: any, record: User) => (
        <Space size="middle">
          <Button type="text" icon={<EditOutlined />} onClick={() => openEditModal(record)} className="text-gray-500 hover:text-primary" title="Edit User" />
          {record.status === 'INACTIVE' ? (
            <Button type="text" icon={<CheckCircleOutlined className="text-green-500" />} onClick={() => handleEnable(record.id)} title="Unblock User" />
          ) : (
            <Button type="text" danger icon={<StopOutlined />} onClick={() => handleDisable(record.id)} title="Block User" />
          )}
        </Space>
      ),
    },
  ];

  const totalUsers = users.length;
  const activeUsers = users.filter(u => u.status === 'ACTIVE').length;
  const blockedUsers = users.filter(u => u.status === 'INACTIVE').length;
  const pendingUsers = users.filter(u => u.status === 'PENDING').length;

  return (
    <div className="bg-transparent h-full flex flex-col space-y-6">
      {/* Massive Beautiful Header */}
      <div className="bg-white p-6 md:p-8 rounded-3xl border border-neutral-200/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative overflow-hidden shrink-0 group">
        <div className="absolute top-0 right-0 -mr-32 -mt-32 w-[500px] h-[500px] rounded-full bg-gradient-to-bl from-primary-200/40 via-primary-50/20 to-transparent blur-3xl opacity-60 pointer-events-none group-hover:scale-110 transition-transform duration-1000"></div>
        <div className="absolute bottom-0 left-0 -ml-32 -mb-32 w-80 h-80 rounded-full bg-gradient-to-tr from-info/10 to-transparent blur-3xl opacity-50 pointer-events-none"></div>
        
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center text-primary shadow-[inset_0_2px_10px_rgba(255,255,255,1),0_4px_15px_rgba(0,160,226,0.2)] border border-primary/20 transform -rotate-12 group-hover:rotate-12 group-hover:scale-110 transition duration-500">
              <i className="ph-fill ph-users-three text-3xl drop-shadow-sm"></i>
            </div>
            <div>
              <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-neutral-900 via-neutral-700 to-neutral-600 tracking-tight m-0 drop-shadow-sm">
                User Management
              </h2>
              <p className="text-neutral-500 text-base font-medium mt-1 mb-0 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-success animate-pulse"></span>
                Manage your organization's members, roles, and access controls in one place.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button 
              icon={<UploadOutlined className="text-lg" />} 
              onClick={() => setIsImportVisible(true)} 
              className="rounded-xl h-11 px-5 border-neutral-200/80 font-bold hover:border-primary hover:text-primary transition shadow-sm bg-white hover:bg-primary-50/50 flex items-center justify-center gap-2"
            >
              Import CSV/XLSX
            </Button>
            <Button 
              icon={<MailOutlined className="text-lg" />} 
              onClick={() => setIsInviteVisible(true)} 
              className="rounded-xl h-11 px-5 border-neutral-200/80 font-bold hover:border-primary hover:text-primary transition shadow-sm bg-white hover:bg-primary-50/50 flex items-center justify-center gap-2"
            >
              Invite User
            </Button>
            <Button 
              type="primary" 
              icon={<UserAddOutlined className="text-lg" />} 
              onClick={openAddModal} 
              className="rounded-xl h-11 px-6 bg-gradient-to-r from-primary to-primary-600 hover:from-primary-500 hover:to-primary-700 shadow-[0_8px_20px_rgba(0,160,226,0.3)] border-0 transition transform hover:-translate-y-1 transform-gpu hover:scale-105 font-bold text-white flex items-center justify-center gap-2"
            >
              Add User
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 shrink-0">
        <div className="bg-white rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary-50/50 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Total Users</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{totalUsers}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-primary-50 text-primary flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-users text-xl"></i>
            </div>
          </div>
          <div className="mt-4 flex items-center text-xs font-semibold text-primary">
            <i className="ph-bold ph-trend-up mr-1"></i> +12% from last month
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-success/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Active</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{activeUsers}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-success/10 text-success flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-check-circle text-xl"></i>
            </div>
          </div>
          <div className="mt-4 flex items-center text-xs font-semibold text-success">
            <div className="w-full bg-neutral-100 rounded-full h-1.5 mt-1 overflow-hidden">
              <div className="bg-success h-1.5 rounded-full" style={{ width: `${(activeUsers/totalUsers)*100 || 0}%` }}></div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-danger/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Blocked</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{blockedUsers}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-danger/10 text-danger flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-prohibit text-xl"></i>
            </div>
          </div>
          <div className="mt-4 flex items-center text-xs font-semibold text-neutral-400">
            Users restricted from login
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-warning/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Pending</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{pendingUsers}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-warning/10 text-warning flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-hourglass text-xl"></i>
            </div>
          </div>
          <div className="mt-4 flex items-center text-xs font-semibold text-warning">
            Awaiting activation
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
            placeholder="Search users by name or email..." 
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full sm:max-w-md h-12 rounded-xl border-neutral-200/80 hover:border-primary focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(0,160,226,0.15)] bg-neutral-50/50 hover:bg-white focus-within:bg-white transition-all text-base font-medium px-4 shadow-[0_2px_10px_rgba(0,0,0,0.02)]"
          />
          <div className="flex items-center gap-2 text-sm font-bold text-neutral-500 bg-neutral-50/80 px-4 py-2 rounded-lg border border-neutral-100">
             <i className="ph-fill ph-users text-primary"></i>
             <span>
                {users.filter(u => (u.username || '').toLowerCase().includes(searchText.toLowerCase()) || (u.email || '').toLowerCase().includes(searchText.toLowerCase())).length} Users Found
             </span>
          </div>
        </div>

        <div className="p-2 flex-1 flex flex-col">
          <Table 
            columns={columns} 
            dataSource={users.filter(u => 
              (u.username || '').toLowerCase().includes(searchText.toLowerCase()) || 
              (u.email || '').toLowerCase().includes(searchText.toLowerCase())
            )} 
            rowKey="id" 
            loading={loading} 
            size="middle" 
            className="flex-1 custom-beautiful-table"
            onChange={(pagination) => {
               sessionStorage.setItem('UserManagement_page', pagination.current?.toString() || '1');
            }}
            pagination={{ 
              pageSize: 10, 
              defaultCurrent: parseInt(sessionStorage.getItem('UserManagement_page') || '1', 10),
              className: 'mt-6 px-4 pb-4',
              showTotal: (total, range) => <span className="font-semibold text-neutral-500">Showing {range[0]}-{range[1]} of {total} users</span>
            }}
            scroll={{ x: 'max-content' }}
          />
        </div>
      </div>

      {/* Add/Edit User Modal */}
      <Modal
        title={
          <div className="flex items-center gap-3 pb-2 border-b border-neutral-100">
            <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center text-primary">
              <i className={`ph-fill ${editingUser ? 'ph-pencil-simple' : 'ph-user-plus'} text-xl`}></i>
            </div>
            <div>
              <h3 className="text-lg font-bold text-neutral-900 m-0">{editingUser ? "Edit User" : "Add New User"}</h3>
              <p className="text-xs text-neutral-500 m-0">{editingUser ? "Update the details of the existing user." : "Fill in the details to create a new user account."}</p>
            </div>
          </div>
        }
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onOk={() => form.submit()}
        okText={editingUser ? "Save Changes" : "Create User"}
        confirmLoading={submitting}
        okButtonProps={{ 
          disabled: submitting, 
          className: "bg-gradient-to-r from-primary to-primary-600 border-0 shadow-md shadow-primary/30 h-10 px-6 font-bold rounded-lg hover:scale-105 transition-transform" 
        }}
        cancelButtonProps={{ disabled: submitting, className: "h-10 px-6 font-semibold rounded-lg" }}
        className="rounded-2xl overflow-hidden"
        width={500}
        closeIcon={<div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-500 hover:bg-neutral-200 hover:text-neutral-900 transition-colors"><i className="ph ph-x"></i></div>}
      >
        <Form form={form} layout="vertical" onFinish={handleAddEdit} className="mt-6">
          <Form.Item name="username" label={<span className="font-bold text-neutral-700">Username</span>} rules={[{ required: true }]}>
            <Input className="rounded-xl h-12 border-neutral-300 hover:border-primary focus:border-primary focus:shadow-[0_0_0_2px_rgba(0,160,226,0.2)] bg-neutral-50 focus:bg-white transition text-base px-4" placeholder="e.g. john_doe" />
          </Form.Item>
          {!editingUser && (
            <>
              <Form.Item name="email" label={<span className="font-bold text-neutral-700">Email Address</span>} rules={[{ required: true, type: 'email' }]}>
                <Input className="rounded-xl h-12 border-neutral-300 hover:border-primary focus:border-primary focus:shadow-[0_0_0_2px_rgba(0,160,226,0.2)] bg-neutral-50 focus:bg-white transition text-base px-4" placeholder="john@company.com" />
              </Form.Item>
              <Form.Item name="password" label={<span className="font-bold text-neutral-700">Initial Password</span>} rules={[{ required: true }]}>
                <Input.Password className="rounded-xl h-12 border-neutral-300 hover:border-primary focus:border-primary focus:shadow-[0_0_0_2px_rgba(0,160,226,0.2)] bg-neutral-50 focus:bg-white transition text-base px-4 py-0" placeholder="••••••••" />
              </Form.Item>
            </>
          )}
          <Form.Item name="roleIds" label={<span className="font-bold text-neutral-700">Assigned Roles</span>}>
            <Select 
              mode="multiple" 
              placeholder="Select roles for this user" 
              className="rounded-xl"
              size="large"
              popupClassName="rounded-xl shadow-xl"
            >
              {roles.map(r => (
                <Select.Option key={r.id} value={r.id}>
                  <div className="flex items-center gap-2 font-medium">
                    <i className="ph-fill ph-shield-check text-primary"></i> {r.name}
                  </div>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* Invite User Modal */}
      <Modal
        title={
          <div className="flex items-center gap-3 pb-2 border-b border-neutral-100">
            <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center text-primary">
              <i className="ph-fill ph-envelope-simple text-xl"></i>
            </div>
            <div>
              <h3 className="text-lg font-bold text-neutral-900 m-0">Invite New User</h3>
              <p className="text-xs text-neutral-500 m-0">Send an invitation email to a new member.</p>
            </div>
          </div>
        }
        open={isInviteVisible}
        onCancel={() => setIsInviteVisible(false)}
        onOk={() => inviteForm.submit()}
        okText="Send Invitation"
        confirmLoading={submitting}
        okButtonProps={{ 
          disabled: submitting,
          className: "bg-gradient-to-r from-primary to-primary-600 border-0 shadow-md shadow-primary/30 h-10 px-6 font-bold rounded-lg hover:scale-105 transition-transform"
        }}
        cancelButtonProps={{ disabled: submitting, className: "h-10 px-6 font-semibold rounded-lg" }}
        className="rounded-2xl overflow-hidden"
        width={500}
        closeIcon={<div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-500 hover:bg-neutral-200 hover:text-neutral-900 transition-colors"><i className="ph ph-x"></i></div>}
      >
        <Form form={inviteForm} layout="vertical" onFinish={handleInvite} className="mt-6">
          <Form.Item name="username" label={<span className="font-bold text-neutral-700">Username</span>} rules={[{ required: true }]}>
            <Input className="rounded-xl h-12 border-neutral-300 focus:border-primary bg-neutral-50 focus:bg-white transition px-4" placeholder="Enter username" />
          </Form.Item>
          <Form.Item name="email" label={<span className="font-bold text-neutral-700">Email Address</span>} rules={[{ required: true, type: 'email' }]}>
            <Input className="rounded-xl h-12 border-neutral-300 focus:border-primary bg-neutral-50 focus:bg-white transition px-4" placeholder="user@company.com" />
          </Form.Item>
          <Form.Item name="password" label={<span className="font-bold text-neutral-700">Temporary Password</span>} rules={[{ required: true, min: 6 }]}>
            <Input.Password className="rounded-xl h-12 border-neutral-300 focus:border-primary bg-neutral-50 focus:bg-white transition px-4 py-0" placeholder="Enter temporary password" />
          </Form.Item>
          <Form.Item name="roleIds" label={<span className="font-bold text-neutral-700">Roles</span>}>
            <Select mode="multiple" placeholder="Select roles" size="large" className="rounded-xl">
              {roles.map(r => (
                <Select.Option key={r.id} value={r.id}>{r.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* Import Users Modal - Compact Premium Redesign */}
      <Modal
        title={null}
        open={isImportVisible}
        onCancel={() => setIsImportVisible(false)}
        footer={null}
        className="rounded-3xl overflow-hidden p-0 fancy-modal"
        width={560}
        closeIcon={
          <div className="w-8 h-8 rounded-full bg-white/20 backdrop-blur-md border border-white/30 flex items-center justify-center text-white hover:bg-danger hover:border-danger transition-all z-50">
            <i className="ph ph-x text-base"></i>
          </div>
        }
        styles={{ body: { padding: 0 } }}
        bodyStyle={{ padding: 0 }}
      >
        <div className="relative overflow-hidden bg-white flex flex-col">
          {/* Header Section - Thinner */}
          <div className="relative p-6 pb-10 bg-gradient-to-br from-primary-600 to-info overflow-hidden shrink-0">
            <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>
            
            <div className="relative z-10 flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white shadow-lg transform -rotate-3 hover:rotate-0 hover:scale-105 transition-all duration-300">
                <i className="ph-fill ph-file-xls text-3xl drop-shadow-sm"></i>
              </div>
              <div>
                <h3 className="text-2xl font-black text-white m-0 tracking-tight drop-shadow-sm">Bulk Import Users</h3>
                <p className="text-primary-100 font-medium m-0 mt-1 text-[13px] opacity-90">Onboard members via spreadsheet</p>
              </div>
            </div>
          </div>
          
          {/* Content Section - Compact */}
          <div className="p-6 -mt-6 bg-white rounded-t-3xl relative z-20 shadow-[0_-10px_20px_rgba(0,0,0,0.05)] flex-1">
            
            {/* Instruction Banner - Ultra Compact */}
            <div className="mb-5 p-3.5 bg-info/5 rounded-xl border border-info/20 flex items-start gap-3">
              <i className="ph-fill ph-info text-info text-xl mt-0.5 shrink-0"></i>
              <div>
                <p className="text-[13px] font-bold text-neutral-800 m-0 mb-1 flex items-center gap-2">
                  Format: <span className="font-mono text-[11px] bg-white px-1.5 py-0.5 rounded border border-neutral-200 text-info font-bold tracking-wide">username, email, password, role1...</span>
                </p>
                <p className="text-[12px] text-neutral-500 m-0 leading-relaxed font-medium">
                  First row is header. <a onClick={handleDownloadTemplate} className="text-primary hover:underline cursor-pointer">Download template (Export)</a> to see the required structure. Extra columns map to roles automatically.
                </p>
              </div>
            </div>

            {/* Upload Dragger - Refined Proportions */}
            <div className="rounded-2xl border-2 border-dashed border-primary/30 hover:border-primary bg-neutral-50/50 hover:bg-primary/5 transition-all duration-300 overflow-hidden group">
              <Upload.Dragger
                name="file"
                accept=".csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="overflow-hidden"
                style={{ border: 'none', background: 'transparent' }}
                showUploadList={false}
                customRequest={async ({ file, onSuccess, onError }: any) => {
                try {
                  let uploadFile = file;
                  const isExcel = file.name.endsWith('.xlsx') || file.type.includes('spreadsheetml');
                  
                  if (isExcel) {
                    const buffer = await file.arrayBuffer();
                    const workbook = XLSX.read(buffer, { type: 'array' });
                    const firstSheetName = workbook.SheetNames[0];
                    const worksheet = workbook.Sheets[firstSheetName];
                    const csvData = XLSX.utils.sheet_to_csv(worksheet);
                    uploadFile = new File([csvData], file.name.replace('.xlsx', '.csv'), { type: 'text/csv' });
                  }

                  const formData = new FormData();
                  formData.append('file', uploadFile);
                  
                  const res = await api.post('/users/import', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                  });
                  
                  message.success(`Imported ${res.data.data.successCount} users. Failed: ${res.data.data.failureCount}`);
                  
                  if (res.data.data.failureCount > 0) {
                    Modal.error({
                      title: 'Import Errors Detected',
                      width: 600,
                      content: (
                        <div className="mt-4">
                          <p className="mb-3 text-neutral-600 font-medium text-[14px]">
                            Please fix the following issues in your file:
                          </p>
                          <div className="max-h-72 overflow-y-auto text-[13px] text-danger bg-danger/5 border border-danger/20 p-3 rounded-xl font-mono">
                            {res.data.data.errors.map((e: string, i: number) => (
                              <div key={i} className="mb-2 pb-2 border-b border-danger/10 last:border-0 last:mb-0 last:pb-0 flex items-start gap-2">
                                <i className="ph-fill ph-warning-circle mt-0.5 shrink-0"></i>
                                <span>{e}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ),
                      okButtonProps: { className: 'rounded-xl h-10 px-6 font-bold' }
                    });
                  } else {
                    setIsImportVisible(false);
                  }
                  
                  onSuccess();
                  fetchUsers();
                } catch (err) {
                  message.error('File import failed. Please check format.');
                  onError(err);
                }
              }}
            >
              <div className="py-10 px-6 flex flex-col items-center justify-center relative">
                <div className="w-20 h-20 mb-4 relative flex items-center justify-center transform group-hover:-translate-y-1 transition-transform duration-300">
                  <div className="absolute inset-0 bg-primary/20 rounded-full blur-xl group-hover:bg-primary/30 transition-colors"></div>
                  <div className="w-16 h-16 bg-white rounded-2xl shadow-[0_8px_20px_rgba(0,160,226,0.12)] border border-primary/10 flex items-center justify-center text-primary relative z-10 rotate-3 group-hover:rotate-6 transition-transform duration-300">
                    <UploadOutlined className="text-3xl drop-shadow-sm" />
                  </div>
                </div>
                <h4 className="text-lg font-black text-neutral-800 m-0 mb-1 relative z-10">Select or drop file</h4>
                <p className="text-neutral-500 font-medium text-[13px] text-center max-w-[250px] relative z-10">
                  Upload <span className="font-bold text-info">.CSV</span> or <span className="font-bold text-success">.XLSX</span> files.
                </p>
              </div>
              </Upload.Dragger>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};
