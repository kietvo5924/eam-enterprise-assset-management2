import React, { useState, useEffect } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, message, Popconfirm, Select } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, FilterOutlined } from '@ant-design/icons';
import api from '../../../utils/axios';

interface SparePart {
  id: string;
  name: string;
  partNumber: string;
  description?: string;
  quantityInStock: number;
  unitCost: number;
}

export const SparePartsManagement: React.FC = () => {
  const [parts, setParts] = useState<SparePart[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [filterStock, setFilterStock] = useState('all');

  const fetchParts = async () => {
    setLoading(true);
    try {
      const response = await api.get('/spare-parts');
      if (response.data.success) {
        setParts(response.data.data);
      }
    } catch (error) {
      message.error('Failed to load spare parts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchParts();
  }, []);

  const handleCreateOrUpdate = async (values: any) => {
    try {
      if (editingId) {
        await api.put(`/spare-parts/${editingId}`, values);
        message.success('Spare part updated successfully');
      } else {
        await api.post('/spare-parts', values);
        message.success('Spare part created successfully');
      }
      setIsModalVisible(false);
      form.resetFields();
      fetchParts();
    } catch (error) {
      message.error('Failed to save spare part');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/spare-parts/${id}`);
      message.success('Spare part deleted successfully');
      fetchParts();
    } catch (error) {
      message.error('Failed to delete spare part');
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: SparePart, b: SparePart) => a.name.localeCompare(b.name),
      render: (text: string) => <span className="font-semibold text-neutral-800">{text}</span>,
    },
    {
      title: 'Part Number',
      dataIndex: 'partNumber',
      key: 'partNumber',
      sorter: (a: SparePart, b: SparePart) => a.partNumber.localeCompare(b.partNumber),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'In Stock',
      dataIndex: 'quantityInStock',
      key: 'quantityInStock',
      sorter: (a: SparePart, b: SparePart) => a.quantityInStock - b.quantityInStock,
    },
    {
      title: 'Unit Cost',
      dataIndex: 'unitCost',
      key: 'unitCost',
      sorter: (a: SparePart, b: SparePart) => a.unitCost - b.unitCost,
      render: (val: number) => val ? `$${val.toFixed(2)}` : '-',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: SparePart) => (
        <Space size="middle">
          <Button 
            type="text" 
            icon={<EditOutlined />} 
            onClick={() => {
              setEditingId(record.id);
              form.setFieldsValue(record);
              setIsModalVisible(true);
            }} 
          />
          <Popconfirm
            title="Delete this part?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
            okButtonProps={{ danger: true }}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div className="flex justify-between items-center mb-6">
        <div>
          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-[0.18em] mb-1">INVENTORY</p>
          <h2 className="text-[26px] leading-tight font-black text-neutral-900 tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-500 text-2xl shrink-0">
              <i className="ph-fill ph-package"></i>
            </div>
            Spare Parts Management
          </h2>
        </div>
        <Button
          type="primary"
          onClick={() => {
            setEditingId(null);
            form.resetFields();
            setIsModalVisible(true);
          }}
          icon={<PlusOutlined />}
          className="rounded-xl h-10 px-5 font-bold flex items-center justify-center gap-2 shadow-sm"
        >
          New Part
        </Button>
      </div>

      <div className="flex gap-4 mb-4 items-center">
        <Input
          placeholder="Tìm kiếm theo Tên hoặc Mã vật tư..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          prefix={<SearchOutlined className="text-neutral-400" />}
          className="w-80 h-10 rounded-xl"
          allowClear
        />
        <Select
          value={filterStock}
          onChange={setFilterStock}
          className="w-48 h-10 [&_.ant-select-selector]:rounded-xl"
          options={[
            { value: 'all', label: 'Tất cả trạng thái kho' },
            { value: 'instock', label: 'Còn hàng' },
            { value: 'low', label: 'Sắp hết (≤ 10)' },
            { value: 'out', label: 'Hết hàng (0)' },
          ]}
        />
      </div>

      <div className="flex-1 overflow-auto bg-white border border-neutral-200 rounded-3xl p-4 shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
        <Table
          dataSource={parts.filter(part => {
            const matchSearch = part.name.toLowerCase().includes(searchText.toLowerCase()) || 
                                part.partNumber.toLowerCase().includes(searchText.toLowerCase());
            let matchStock = true;
            if (filterStock === 'out') matchStock = part.quantityInStock === 0;
            if (filterStock === 'low') matchStock = part.quantityInStock > 0 && part.quantityInStock <= 10;
            if (filterStock === 'instock') matchStock = part.quantityInStock > 0;
            return matchSearch && matchStock;
          })}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </div>

      <Modal
        title={editingId ? 'Edit Spare Part' : 'Create Spare Part'}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={null}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={handleCreateOrUpdate}>
          <Form.Item name="name" label="Part Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Engine Oil Filter" />
          </Form.Item>
          <Form.Item name="partNumber" label="Part Number" rules={[{ required: true }]}>
            <Input placeholder="e.g. FLT-001" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <div className="flex gap-4">
            <Form.Item name="quantityInStock" label="Quantity In Stock" rules={[{ required: true }]} className="flex-1">
              <InputNumber min={0} className="w-full" />
            </Form.Item>
            <Form.Item name="unitCost" label="Unit Cost ($)" rules={[{ required: true }]} className="flex-1">
              <InputNumber min={0} step={0.01} className="w-full" />
            </Form.Item>
          </div>
          <Form.Item className="mb-0 text-right">
            <Button onClick={() => setIsModalVisible(false)} className="mr-2">Cancel</Button>
            <Button type="primary" htmlType="submit">Save</Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
