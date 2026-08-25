import React, { useState, useEffect } from 'react';
import { Table, DatePicker, Select, Input, Button, Tag, Space, Form, Drawer, Descriptions } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import api from '../../../utils/axios';

const { RangePicker } = DatePicker;

interface AuditLog {
  id: string;
  userId: string;
  username?: string;
  actionType: string;
  entityType: string;
  entityId: string;
  timestamp: string;
}

export const AuditLogViewer: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    current: parseInt(sessionStorage.getItem('AuditLogViewer_page') || '1', 10),
    pageSize: 20,
    total: 0,
  });

  const [form] = Form.useForm();
  
  // Drawer state
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  const showDetails = (log: AuditLog) => {
    setSelectedLog(log);
    setDrawerVisible(true);
  };

  const fetchLogs = async (page = 1, pageSize = 20, values: any = {}) => {
    setLoading(true);
    try {
      const params: any = {
        page: page - 1,
        size: pageSize,
        ...values,
      };
      
      // Handle date range
      if (values.dateRange && values.dateRange.length === 2) {
        params.startDate = values.dateRange[0].toISOString();
        params.endDate = values.dateRange[1].toISOString();
        delete params.dateRange;
      }

      const response = await api.get('/audit-logs', { params });
      
      if (response.data.success) {
        setLogs(response.data.data.content);
        const currentPage = response.data.data.currentPage + 1;
        setPagination({
          current: currentPage,
          pageSize: pageSize,
          total: response.data.data.totalElements,
        });
        sessionStorage.setItem('AuditLogViewer_page', currentPage.toString());
      }
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs(pagination.current, pagination.pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTableChange = (newPagination: any) => {
    fetchLogs(newPagination.current, newPagination.pageSize, form.getFieldsValue());
  };

  const onFinish = (values: any) => {
    fetchLogs(1, pagination.pageSize, values);
  };

  const onReset = () => {
    form.resetFields();
    fetchLogs(1, pagination.pageSize);
  };

  const getActionColor = (action: string) => {
    switch (action) {
      case 'CREATE': return 'green';
      case 'UPDATE': return 'blue';
      case 'DELETE': return 'red';
      default: return 'default';
    }
  };

  const columns: ColumnsType<AuditLog> = [
    {
      title: 'Time',
      dataIndex: 'timestamp',
      key: 'timestamp',
      sorter: (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
      render: (text) => dayjs(text).format('YYYY-MM-DD HH:mm:ss'),
      width: 180,
    },
    {
      title: 'User',
      dataIndex: 'userId',
      key: 'userId',
      sorter: (a, b) => (a.username || a.userId).localeCompare(b.username || b.userId),
      render: (_, record) => (
        <span className="font-medium text-neutral-800">
          {record.username ? record.username : record.userId}
        </span>
      ),
    },
    {
      title: 'Action',
      dataIndex: 'actionType',
      key: 'actionType',
      sorter: (a, b) => a.actionType.localeCompare(b.actionType),
      filters: [
        { text: 'CREATE', value: 'CREATE' },
        { text: 'UPDATE', value: 'UPDATE' },
        { text: 'DELETE', value: 'DELETE' },
      ],
      onFilter: (value, record) => record.actionType === value,
      render: (action) => (
        <Tag color={getActionColor(action)} className="font-bold border-0">
          {action}
        </Tag>
      ),
      width: 100,
    },
    {
      title: 'Entity',
      dataIndex: 'entityType',
      key: 'entityType',
      sorter: (a, b) => a.entityType.localeCompare(b.entityType),
      render: (text) => <span className="text-neutral-600 font-semibold">{text}</span>,
    },
    {
      title: 'Entity ID',
      dataIndex: 'entityId',
      key: 'entityId',
      render: (text) => <span className="text-xs text-neutral-500 font-mono bg-neutral-100 px-1.5 py-0.5 rounded">{text}</span>,
    },
    {
      title: 'Action',
      key: 'actions',
      render: (_, record) => (
        <Button type="link" size="small" onClick={() => showDetails(record)} className="px-0">
          Chi tiết
        </Button>
      ),
      width: 100,
    },
  ];

  const creates = logs.filter(l => l.actionType === 'CREATE').length;
  const updates = logs.filter(l => l.actionType === 'UPDATE').length;
  const deletes = logs.filter(l => l.actionType === 'DELETE').length;

  return (
    <div className="space-y-6 h-full flex flex-col relative z-0">
      {/* Page Header */}
      <div className="bg-white p-6 md:p-8 rounded-3xl border border-neutral-200/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative overflow-hidden shrink-0 group">
        <div className="absolute top-0 right-0 -mr-32 -mt-32 w-[500px] h-[500px] rounded-full bg-gradient-to-bl from-primary-200/40 via-primary-50/20 to-transparent blur-3xl opacity-60 pointer-events-none group-hover:scale-110 transition-transform duration-1000"></div>
        
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center text-primary shadow-[inset_0_2px_10px_rgba(255,255,255,1),0_4px_15px_rgba(0,160,226,0.2)] border border-primary/20 transform -rotate-12 group-hover:rotate-12 group-hover:scale-110 transition duration-500">
              <i className="ph-fill ph-file-text text-3xl drop-shadow-sm"></i>
            </div>
            <div>
              <h1 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-neutral-900 via-neutral-700 to-neutral-600 tracking-tight m-0 drop-shadow-sm">
                Audit Logs
              </h1>
              <p className="text-neutral-500 text-base font-medium mt-1 mb-0 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-success animate-pulse"></span>
                Monitor system activities, operations, and data changes securely.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 sm:gap-6 shrink-0">
        <div className="bg-white  rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary-50/50 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Total Loaded</p>
              <h3 className="text-3xl font-black text-neutral-900 m-0">{logs.length}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-primary-50 text-primary flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-list-numbers text-xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-white  rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-success/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Creates</p>
              <h3 className="text-3xl font-black text-success m-0">{creates}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-success/10 text-success flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-plus-circle text-xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-white  rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-info/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Updates</p>
              <h3 className="text-3xl font-black text-info m-0">{updates}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-info/10 text-info flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-pencil-circle text-xl"></i>
            </div>
          </div>
        </div>

        <div className="bg-white  rounded-2xl p-5 border border-neutral-200/60 shadow-sm hover:shadow-md transition relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-danger/10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
          <div className="flex justify-between items-start relative z-10">
            <div>
              <p className="text-sm font-bold text-neutral-500 uppercase tracking-wider mb-1">Deletes</p>
              <h3 className="text-3xl font-black text-danger m-0">{deletes}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-danger/10 text-danger flex items-center justify-center shadow-inner">
              <i className="ph-fill ph-trash text-xl"></i>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-3xl border border-neutral-200/60 shadow-[0_8px_30px_rgb(0,0,0,0.03)] flex-1 flex flex-col overflow-hidden relative">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary-300 via-primary-500 to-primary-600"></div>
        {/* Filter Bar */}
        <div className="p-4 md:p-5 border-b border-neutral-100/80 bg-white/40 backdrop-blur-md shrink-0 relative z-10">
          <Form
            form={form}
            layout="inline"
            onFinish={onFinish}
            className="flex flex-wrap gap-3"
          >
            <Form.Item name="actionType" className="mb-0">
              <Select placeholder="Filter by Action" className="w-[160px] h-10" allowClear>
                <Select.Option value="CREATE">CREATE</Select.Option>
                <Select.Option value="UPDATE">UPDATE</Select.Option>
                <Select.Option value="DELETE">DELETE</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="entityType" className="mb-0">
              <Input placeholder="Entity Type (e.g., User)" className="w-[200px] h-10 rounded-lg border-neutral-300 hover:border-primary focus:border-primary" allowClear />
            </Form.Item>
            <Form.Item name="username" className="mb-0">
              <Input placeholder="User Name / Email" className="w-[200px] h-10 rounded-lg border-neutral-300 hover:border-primary focus:border-primary" allowClear />
            </Form.Item>
            <Form.Item name="dateRange" className="mb-0">
              <RangePicker showTime className="h-10 rounded-lg border-neutral-300 hover:border-primary focus:border-primary" />
            </Form.Item>
            <Form.Item className="mb-0 ml-auto mr-0">
              <Space>
                <Button onClick={onReset} className="h-10 px-5 rounded-lg font-semibold">Reset</Button>
                <Button type="primary" htmlType="submit" className="h-10 px-6 rounded-lg bg-primary font-bold shadow-md shadow-primary/30">
                  Filter
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </div>

        {/* Data Table */}
        <div className="flex-1 flex flex-col p-2">
          <Table
            columns={columns}
            dataSource={logs}
            rowKey="id"
            pagination={pagination}
            loading={loading}
            onChange={handleTableChange}
            size="middle"
            className="flex-1 custom-beautiful-table"
            scroll={{ x: 'max-content' }}
          />
        </div>
      </div>

      {/* Details Drawer */}
      <Drawer
        title={<span className="font-bold text-neutral-800">Chi tiết Sự kiện</span>}
        placement="right"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        size="large"
        destroyOnHidden
      >
        {selectedLog && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 bg-neutral-50 p-4 rounded-lg border border-neutral-100">
              <div className="bg-white p-3 rounded-full shadow-sm">
                <i className={`ph-fill text-2xl ${
                  selectedLog.actionType === 'CREATE' ? 'ph-plus-circle text-green-500' :
                  selectedLog.actionType === 'UPDATE' ? 'ph-pencil-circle text-blue-500' :
                  'ph-trash text-red-500'
                }`}></i>
              </div>
              <div>
                <h3 className="m-0 font-bold text-neutral-800">Thao tác {selectedLog.actionType}</h3>
                <p className="m-0 text-sm text-neutral-500">{dayjs(selectedLog.timestamp).format('DD/MM/YYYY HH:mm:ss')}</p>
              </div>
            </div>

            <Descriptions column={1} bordered size="middle" labelStyle={{ width: '140px', fontWeight: 600, color: '#475569' }}>
              <Descriptions.Item label="Mã sự kiện">
                <span className="font-mono text-xs">{selectedLog.id}</span>
              </Descriptions.Item>
              <Descriptions.Item label="Loại thao tác">
                <Tag color={getActionColor(selectedLog.actionType)} className="font-bold border-0">
                  {selectedLog.actionType}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Người thực hiện">
                <div className="flex flex-col gap-1">
                  {selectedLog.username && <span className="font-bold text-neutral-800">{selectedLog.username}</span>}
                  <span className="font-mono text-xs bg-neutral-100 px-2 py-1 rounded inline-block w-fit text-neutral-500">ID: {selectedLog.userId}</span>
                </div>
              </Descriptions.Item>
              <Descriptions.Item label="Loại dữ liệu">
                <span className="font-semibold text-neutral-700">{selectedLog.entityType}</span>
              </Descriptions.Item>
              <Descriptions.Item label="Mã dữ liệu">
                <span className="font-mono text-xs bg-neutral-100 px-2 py-1 rounded">{selectedLog.entityId}</span>
              </Descriptions.Item>
            </Descriptions>

            <div className="bg-blue-50 text-blue-800 p-4 rounded-lg text-sm flex gap-3 mt-4">
              <i className="ph-fill ph-info text-lg shrink-0"></i>
              <p className="m-0">
                Nhật ký truy vết được tối ưu hóa hiển thị. Dữ liệu thay đổi chi tiết cấp độ trường (field-level change) được lược bỏ theo chuẩn MVP.
              </p>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
};
