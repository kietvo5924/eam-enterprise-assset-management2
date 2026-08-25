import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Switch, message, Space, Popconfirm, Tabs, Tooltip, Select } from 'antd';
import { EditOutlined, PlusOutlined, LockOutlined, UnlockOutlined } from '@ant-design/icons';
import { useAssetStore, type AssetCategory, type HierarchyTemplate, type Location } from '../store/useAssetStore';

export const AssetCategoryManagement: React.FC = () => {
  const {
    categories, templates, locations, loadingCategories, loadingTemplates, loadingLocations,
    fetchCategories, fetchTemplates, fetchLocations,
    createCategory, updateCategory,
    createTemplate, updateTemplate,
    createLocation, updateLocation
  } = useAssetStore();

  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem('assetConfigActiveTab') || 'categories';
  });
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingItem, setEditingItem] = useState<AssetCategory | HierarchyTemplate | Location | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [form] = Form.useForm();

  const [expandedRowKeys, setExpandedRowKeys] = useState<readonly React.Key[]>(() => {
    try {
      const saved = sessionStorage.getItem('AssetLoc_expanded');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const handleExpandedRowsChange = (keys: readonly React.Key[]) => {
    setExpandedRowKeys(keys);
    sessionStorage.setItem('AssetLoc_expanded', JSON.stringify(keys));
  };

  const categoryColumns = React.useMemo(() => [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: AssetCategory, b: AssetCategory) => a.name.localeCompare(b.name),
      render: (text: string) => <span className="font-semibold text-neutral-800">{text}</span>,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      sorter: (a: AssetCategory, b: AssetCategory) => (a.description || '').localeCompare(b.description || ''),
    },
    {
      title: 'Status',
      dataIndex: 'isActive',
      key: 'isActive',
      filters: [
        { text: 'Active', value: true },
        { text: 'Inactive', value: false },
      ],
      onFilter: (value: boolean | React.Key, record: AssetCategory) => record.isActive === value,
      render: (isActive: boolean) => (
        <span className={`px-2 py-1 rounded text-xs font-bold ${isActive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {isActive ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_: any, record: AssetCategory) => (
        <Space size="middle">
          <Tooltip title="Edit Category">
            <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} className="text-primary hover:text-primary-600 hover:bg-primary-50" />
          </Tooltip>
          <Popconfirm
            title={`Are you sure you want to ${record.isActive ? 'block' : 'unblock'} this category?`}
            onConfirm={() => handleToggleStatus(record, 'categories')}
            okText="Yes"
            cancelText="No"
            okButtonProps={{ danger: record.isActive }}
          >
            <Tooltip title={record.isActive ? "Block Category" : "Unblock Category"}>
              <Button
                type="text"
                danger={record.isActive}
                className={!record.isActive ? "text-green-600 hover:text-green-700 hover:bg-green-50" : ""}
                icon={record.isActive ? <LockOutlined /> : <UnlockOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ], []);

  const templateColumns = React.useMemo(() => [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: HierarchyTemplate, b: HierarchyTemplate) => a.name.localeCompare(b.name),
      render: (text: string) => <span className="font-semibold text-neutral-800">{text}</span>,
    },
    {
      title: 'Path Structure',
      dataIndex: 'path',
      key: 'path',
      sorter: (a: HierarchyTemplate, b: HierarchyTemplate) => a.path.localeCompare(b.path),
      render: (text: string) => <span className="font-mono text-xs bg-neutral-100 px-2 py-1 rounded">{text}</span>,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      sorter: (a: HierarchyTemplate, b: HierarchyTemplate) => (a.description || '').localeCompare(b.description || ''),
    },
    {
      title: 'Status',
      dataIndex: 'isActive',
      key: 'isActive',
      filters: [
        { text: 'Active', value: true },
        { text: 'Inactive', value: false },
      ],
      onFilter: (value: boolean | React.Key, record: HierarchyTemplate) => record.isActive === value,
      render: (isActive: boolean) => (
        <span className={`px-2 py-1 rounded text-xs font-bold ${isActive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {isActive ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_: any, record: HierarchyTemplate) => (
        <Space size="middle">
          <Tooltip title="Edit Template">
            <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} className="text-primary hover:text-primary-600 hover:bg-primary-50" />
          </Tooltip>
          <Popconfirm
            title={`Are you sure you want to ${record.isActive ? 'block' : 'unblock'} this template?`}
            onConfirm={() => handleToggleStatus(record, 'templates')}
            okText="Yes"
            cancelText="No"
            okButtonProps={{ danger: record.isActive }}
          >
            <Tooltip title={record.isActive ? "Block Template" : "Unblock Template"}>
              <Button
                type="text"
                danger={record.isActive}
                className={!record.isActive ? "text-green-600 hover:text-green-700 hover:bg-green-50" : ""}
                icon={record.isActive ? <LockOutlined /> : <UnlockOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ], []);

  const locationColumns = React.useMemo(() => [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: Location, b: Location) => a.name.localeCompare(b.name),
      render: (text: string, record: any) => (
        <div className="flex flex-col">
          <span className="font-semibold text-neutral-800 flex items-center gap-2">
            {!record.parentId && !searchText ? <i className="ph-fill ph-buildings text-neutral-400"></i> : <i className="ph-fill ph-factory text-neutral-400"></i>}
            {text}
          </span>
          {searchText && record.parentId && (
            <span className="text-[10px] text-neutral-400 font-mono mt-0.5 truncate" title={record.parentId}>Thuộc: {record.parentId}</span>
          )}
        </div>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'Status',
      dataIndex: 'isActive',
      key: 'isActive',
      filters: [
        { text: 'Active', value: true },
        { text: 'Inactive', value: false },
      ],
      onFilter: (value: boolean | React.Key, record: Location) => record.isActive === value,
      render: (isActive: boolean) => (
        <span className={`px-2 py-1 rounded text-xs font-bold ${isActive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {isActive ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_: any, record: Location) => (
        <Space size="middle">
          <Tooltip title="Edit Location">
            <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} className="text-primary hover:text-primary-600 hover:bg-primary-50" />
          </Tooltip>
          <Popconfirm
            title={`Are you sure you want to ${record.isActive ? 'block' : 'unblock'} this location?`}
            onConfirm={() => handleToggleStatus(record, 'locations')}
            okText="Yes"
            cancelText="No"
            okButtonProps={{ danger: record.isActive }}
          >
            <Tooltip title={record.isActive ? "Block Location" : "Unblock Location"}>
              <Button
                type="text"
                danger={record.isActive}
                className={!record.isActive ? "text-green-600 hover:text-green-700 hover:bg-green-50" : ""}
                icon={record.isActive ? <LockOutlined /> : <UnlockOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ], []);

  useEffect(() => {
    fetchCategories();
    fetchTemplates();
    fetchLocations();
  }, [fetchCategories, fetchTemplates, fetchLocations]);

  const handleAdd = () => {
    setEditingItem(null);
    form.resetFields();
    if (activeTab === 'templates') {
      form.setFieldsValue({ pathTags: [''] });
    }
    setIsModalVisible(true);
  };

  const handleEdit = (item: AssetCategory | HierarchyTemplate | Location) => {
    setEditingItem(item);
    form.setFieldsValue({
      name: item.name,
      description: item.description,
      isActive: item.isActive,
      ...('path' in item ? { pathTags: item.path ? item.path.split('.') : [] } : {}),
      ...('parentId' in item ? { parentId: item.parentId } : {})
    });
    setIsModalVisible(true);
  };

  const handleToggleStatus = async (record: any, type: 'categories' | 'templates' | 'locations') => {
    try {
      let success = false;
      const newStatus = !record.isActive;

      if (type === 'categories') {
        success = await updateCategory(record.id, {
          name: record.name,
          description: record.description,
          isActive: newStatus
        });
      } else if (type === 'templates') {
        success = await updateTemplate(record.id, {
          name: record.name,
          description: record.description,
          path: record.path,
          isActive: newStatus
        });
      } else {
        success = await updateLocation(record.id, {
          name: record.name,
          description: record.description,
          parentId: record.parentId,
          isActive: newStatus
        });
      }

      if (success) {
        message.success(`${type.charAt(0).toUpperCase() + type.slice(1, -1)} ${newStatus ? 'unblocked' : 'blocked'} successfully`);
      } else {
        message.error('Failed to change status');
      }
    } catch (error: any) {
      message.error(error.response?.data?.error || 'Operation failed');
    }
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      let success = false;
      const finalValues = { ...values };

      if (activeTab === 'categories') {
        success = editingItem ? await updateCategory(editingItem.id, finalValues) : await createCategory(finalValues);
      } else if (activeTab === 'templates') {
        const formatLtree = (s: string) => {
          let n = s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
          return n.replace(/[^a-zA-Z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
        };
        finalValues.path = values.pathTags ? values.pathTags.map(formatLtree).filter((t: string) => t.length > 0).join('.') : '';
        delete finalValues.pathTags;
        success = editingItem ? await updateTemplate(editingItem.id, finalValues) : await createTemplate(finalValues);
      } else {
        success = editingItem ? await updateLocation(editingItem.id, finalValues) : await createLocation(finalValues);
      }

      if (success) {
        message.success(`Saved successfully`);
        setIsModalVisible(false);
      } else {
        message.error('Operation failed');
      }
    } catch (error: any) {
      if (error.response?.data?.error) {
        message.error(error.response.data.error);
      } else {
        console.error('Form validation failed:', error);
      }
    } finally {
      setSubmitting(false);
    }
  };



  const filteredCategories = categories.filter(c =>
    c.name.toLowerCase().includes(searchText.toLowerCase()) ||
    (c.description || '').toLowerCase().includes(searchText.toLowerCase())
  );

  const filteredTemplates = templates.filter(t =>
    t.name.toLowerCase().includes(searchText.toLowerCase()) ||
    (t.description || '').toLowerCase().includes(searchText.toLowerCase()) ||
    t.path.toLowerCase().includes(searchText.toLowerCase())
  );

  const filteredLocations = locations.filter(l =>
    l.name.toLowerCase().includes(searchText.toLowerCase()) ||
    (l.description || '').toLowerCase().includes(searchText.toLowerCase())
  );

  const locationTreeData = React.useMemo(() => {
    if (searchText) {
      return filteredLocations.map(l => ({ ...l, key: l.id }));
    }

    const formatLtree = (s: string) => {
      if (!s) return '';
      let n = s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      return n.replace(/[^a-zA-Z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
    };
    const getFullPath = (l: Location) => l.parentId ? `${l.parentId}.${formatLtree(l.name)}` : formatLtree(l.name);

    const map = new Map<string, any>();
    const roots: any[] = [];

    locations.forEach(l => {
      map.set(getFullPath(l), { ...l, key: l.id, children: [] });
    });

    locations.forEach(l => {
      const node = map.get(getFullPath(l));
      if (l.parentId) {
        const parent = map.get(l.parentId);
        if (parent) {
          parent.children.push(node);
        } else {
          roots.push(node);
        }
      } else {
        roots.push(node);
      }
    });

    const cleanEmptyChildren = (nodes: any[]) => {
      nodes.forEach(n => {
        if (n.children && n.children.length === 0) {
          delete n.children;
        } else if (n.children) {
          cleanEmptyChildren(n.children);
        }
      });
    };
    cleanEmptyChildren(roots);

    return roots;
  }, [locations, filteredLocations, searchText]);

  return (
    <div className="bg-transparent h-full flex flex-col space-y-6">
      <div className="bg-white backdrop-blur-2xl p-6 md:p-8 rounded-3xl border border-neutral-200/80 shadow-[0_8px_30px_rgb(0,0,0,0.06)] relative overflow-hidden shrink-0 group">
        <div className="absolute top-0 right-0 -mr-32 -mt-32 w-[600px] h-[600px] rounded-full bg-gradient-to-bl from-info/20 via-primary-100/30 to-transparent blur-3xl opacity-70 pointer-events-none group-hover:scale-105 transition-transform duration-1000"></div>

        <div className="absolute bottom-0 left-0 -ml-40 -mb-40 w-96 h-96 rounded-full bg-gradient-to-tr from-primary-200/20 to-transparent blur-3xl opacity-60 pointer-events-none"></div>

        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-info/10 to-info/20 flex items-center justify-center text-info shadow-[inset_0_2px_10px_rgba(255,255,255,1),0_4px_15px_rgba(22,119,255,0.2)] border border-info/20 transform rotate-12 group-hover:-rotate-12 group-hover:scale-110 transition duration-500">
              <i className="ph-fill ph-tag text-3xl drop-shadow-sm"></i>
            </div>
            <div>
              <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-neutral-900 via-neutral-800 to-neutral-700 tracking-tight m-0 drop-shadow-sm">
                Asset Configuration
              </h2>
              <p className="text-neutral-500 text-base font-medium mt-1 mb-0 flex items-center gap-2">
                <i className="ph-fill ph-cube text-neutral-400"></i>
                Manage asset categories and hierarchy templates.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="primary"
              icon={<PlusOutlined className="text-lg" />}
              onClick={handleAdd}
              className="rounded-xl h-10 px-6 bg-gradient-to-r from-primary to-primary-600 hover:from-primary-500 hover:to-primary-700 shadow-[0_8px_20px_rgba(0,160,226,0.35)] border-0 transition transform hover:-translate-y-1 transform-gpu font-bold text-white flex items-center justify-center gap-2 text-base hover:scale-105"
            >
              Create {activeTab.replace('categories', 'Category').replace('templates', 'Template').replace('locations', 'Location')}
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6 shrink-0">
        <div className="bg-gradient-to-br from-white to-neutral-50/80 rounded-2xl p-6 border border-neutral-200/80 shadow-sm hover:shadow-lg transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-center relative z-10">
            <div>
              <p className="text-sm font-extrabold text-neutral-400 uppercase tracking-widest mb-2">Total Categories</p>
              <h3 className="text-4xl font-black text-neutral-900 m-0">{categories.length}</h3>
            </div>
            <div className="w-14 h-14 rounded-full bg-white shadow-[0_4px_15px_rgba(0,0,0,0.05)] border border-neutral-100 flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
              <i className="ph-fill ph-folders text-2xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-white to-success/5 rounded-2xl p-6 border border-success/20 shadow-sm hover:shadow-lg transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-success/10 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-center relative z-10">
            <div>
              <p className="text-sm font-extrabold text-success/70 uppercase tracking-widest mb-2">Active Categories</p>
              <h3 className="text-4xl font-black text-success m-0">{categories.filter(c => c.isActive).length}</h3>
            </div>
            <div className="w-14 h-14 rounded-full bg-white shadow-[0_4px_15px_rgba(82,196,26,0.1)] border border-success/20 flex items-center justify-center text-success group-hover:scale-110 transition-transform">
              <i className="ph-fill ph-check-circle text-2xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-white to-info/5 rounded-2xl p-6 border border-info/20 shadow-sm hover:shadow-lg transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-info/10 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-center relative z-10">
            <div>
              <p className="text-sm font-extrabold text-info/70 uppercase tracking-widest mb-2">Total Templates</p>
              <h3 className="text-4xl font-black text-info m-0">{templates.length}</h3>
            </div>
            <div className="w-14 h-14 rounded-full bg-white shadow-[0_4px_15px_rgba(22,119,255,0.1)] border border-info/20 flex items-center justify-center text-info group-hover:scale-110 transition-transform">
              <i className="ph-fill ph-tree-structure text-2xl"></i>
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
            placeholder={`Search ${activeTab}...`}
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full sm:max-w-md h-12 rounded-xl border-neutral-200/80 hover:border-primary focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(0,160,226,0.15)] bg-neutral-50/50 hover:bg-white focus-within:bg-white transition-all text-base font-medium px-4 shadow-[0_2px_10px_rgba(0,0,0,0.02)]"
          />
          <div className="flex items-center gap-2 text-sm font-bold text-neutral-500 bg-neutral-50/80 px-4 py-2 rounded-lg border border-neutral-100">
            <i className="ph-fill ph-tag text-primary"></i>
            <span>
              {activeTab === 'categories' ? filteredCategories.length : (activeTab === 'templates' ? filteredTemplates.length : filteredLocations.length)} Items Found
            </span>
          </div>
        </div>

        <div className="p-3 flex-1 flex flex-col">
          <Tabs
            activeKey={activeTab}
            onChange={(key) => {
              setActiveTab(key);
              localStorage.setItem('assetConfigActiveTab', key);
            }}
            items={[
              {
                key: 'categories',
                label: <span className="font-bold px-4">Categories</span>,
                children: (
                  <Table
                    columns={categoryColumns}
                    dataSource={filteredCategories}
                    rowKey="id"
                    loading={loadingCategories}
                    className="custom-beautiful-table"
                    onChange={(pagination) => sessionStorage.setItem('AssetCat_page', pagination.current?.toString() || '1')}
                    pagination={{ pageSize: 10, defaultCurrent: parseInt(sessionStorage.getItem('AssetCat_page') || '1', 10) }}
                    scroll={{ x: 'max-content' }}
                  />
                )
              },
              {
                key: 'templates',
                label: <span className="font-bold px-4">Hierarchy Templates</span>,
                children: (
                  <Table
                    columns={templateColumns}
                    dataSource={filteredTemplates}
                    rowKey="id"
                    loading={loadingTemplates}
                    className="custom-beautiful-table"
                    onChange={(pagination) => sessionStorage.setItem('AssetTpl_page', pagination.current?.toString() || '1')}
                    pagination={{ pageSize: 10, defaultCurrent: parseInt(sessionStorage.getItem('AssetTpl_page') || '1', 10) }}
                    scroll={{ x: 'max-content' }}
                  />
                )
              },
              {
                key: 'locations',
                label: <span className="font-bold px-4">Locations</span>,
                children: (
                  <Table
                    columns={locationColumns}
                    dataSource={locationTreeData}
                    rowKey="id"
                    loading={loadingLocations}
                    className="custom-beautiful-table"
                    expandable={{ expandedRowKeys, onExpandedRowsChange: handleExpandedRowsChange }}
                    onChange={(pagination) => sessionStorage.setItem('AssetLoc_page', pagination.current?.toString() || '1')}
                    pagination={{ pageSize: 10, defaultCurrent: parseInt(sessionStorage.getItem('AssetLoc_page') || '1', 10) }}
                    scroll={{ x: 'max-content' }}
                  />
                )
              }
            ]}
          />
        </div>
      </div>

      <Modal
        title={
          <div className="flex items-center gap-3 pb-3 border-b border-neutral-100">
            <div>
              <h3 className="text-xl font-black text-neutral-900 m-0">{editingItem ? "Edit" : "Create New"} {activeTab.replace('categories', 'Category').replace('templates', 'Template').replace('locations', 'Location')}</h3>
            </div>
          </div>
        }
        open={isModalVisible}
        onOk={handleOk}
        onCancel={() => setIsModalVisible(false)}
        confirmLoading={submitting}
        footer={[
          <Button key="submit" type="primary" onClick={handleOk} loading={submitting} className="rounded-xl h-10 px-8 bg-primary font-bold">
            {editingItem ? 'Save Changes' : 'Create'}
          </Button>
        ]}
        className="rounded-[24px] overflow-hidden fancy-modal"
      >
        <Form form={form} layout="vertical" className="mt-6 px-2" validateTrigger="onBlur">
          <Form.Item
            name="name"
            label={<span className="font-extrabold text-neutral-700 text-sm uppercase">Name</span>}
            rules={[{ required: true, message: 'Please enter a name' }]}
          >
            <Input className="rounded-xl h-12" placeholder="Name..." />
          </Form.Item>

          {activeTab === 'templates' && (
            <div className="mb-6">
              <div className="mb-2">
                <span className="font-extrabold text-neutral-700 text-sm uppercase">Cấu trúc phân nhánh (Path Structure)</span>
                <p className="text-xs text-neutral-500 mt-1 mb-0">Thêm các cấp bậc từ cao xuống thấp (Ví dụ: Nhà máy &gt; Xưởng &gt; Máy móc)</p>
              </div>
              <Form.List name="pathTags" initialValue={['']}>
                {(fields, { add, remove }) => (
                  <div className="space-y-2">
                    {fields.map((field, index) => (
                      <div key={field.key} className="flex gap-2 items-start">
                        <div className="shrink-0 mt-2 bg-neutral-100 rounded-lg px-2.5 py-1 text-xs font-bold text-neutral-500 border border-neutral-200">
                          Cấp {index + 1}
                        </div>
                        <Form.Item
                          {...field}
                          className="mb-0 flex-1"
                          rules={[{ required: true, message: 'Vui lòng nhập tên cấp' }]}
                        >
                          <Input className="rounded-xl h-10" placeholder={`VD: ${index === 0 ? 'Nhà máy' : index === 1 ? 'Xưởng' : 'Máy móc'}...`} />
                        </Form.Item>
                        <Button
                          type="text"
                          danger
                          className="shrink-0 mt-1"
                          icon={<i className="ph-bold ph-x text-base"></i>}
                          onClick={() => remove(field.name)}
                          disabled={fields.length <= 1}
                        />
                      </div>
                    ))}
                    <Button
                      type="dashed"
                      onClick={() => add()}
                      block
                      icon={<PlusOutlined />}
                      className="rounded-xl h-10 mt-2 border-primary/30 text-primary hover:text-primary-600 hover:border-primary font-semibold bg-primary/5"
                    >
                      Thêm cấp con
                    </Button>
                  </div>
                )}
              </Form.List>
            </div>
          )}

          {activeTab === 'locations' && (
            <Form.Item
              name="parentId"
              label={<span className="font-extrabold text-neutral-700 text-sm uppercase">Vị trí cấp trên (Parent Location)</span>}
              rules={[{ required: false }]}
              extra={<span className="text-xs text-neutral-500">Bỏ trống nếu đây là Vị trí gốc (Top-level Location)</span>}
            >
              <Select
                allowClear
                showSearch
                className="rounded-xl h-12"
                placeholder="Chọn vị trí cấp trên..."
                options={locations
                  .filter(l => !editingItem || l.id !== editingItem.id) // Cannot be parent of itself
                  .map(l => {
                    const formatLtree = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9_]/g, '_');
                    const fullPath = l.parentId ? `${l.parentId}.${formatLtree(l.name)}` : formatLtree(l.name);
                    return { value: fullPath, label: `${l.name} (${fullPath})` };
                  })
                }
              />
            </Form.Item>
          )}

          <Form.Item
            name="description"
            label={<span className="font-extrabold text-neutral-700 text-sm uppercase">Description</span>}
          >
            <Input.TextArea className="rounded-xl" rows={3} placeholder="Description..." />
          </Form.Item>

          <Form.Item
            name="isActive"
            label={<span className="font-extrabold text-neutral-700 text-sm uppercase">Active Status</span>}
            valuePropName="checked"
            initialValue={true}
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
