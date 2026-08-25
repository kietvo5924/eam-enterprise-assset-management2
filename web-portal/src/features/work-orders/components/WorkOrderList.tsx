import React, { useEffect, useState } from 'react';
import { Table, Button, Tag, Input, message, Popconfirm, Tooltip } from 'antd';
import { PlusOutlined, CheckCircleOutlined, PlayCircleOutlined, EyeOutlined, EditOutlined, DeleteOutlined, UserSwitchOutlined } from '@ant-design/icons';
import { useWorkOrderStore } from '../store/useWorkOrderStore';
import CreateWorkOrderDrawer from './CreateWorkOrderDrawer';
import AssignWorkOrderModal from './AssignWorkOrderModal';
import WorkOrderDetailDrawer from './WorkOrderDetailDrawer';
import dayjs from 'dayjs';
const WorkOrderList: React.FC = () => {
  const { workOrders, loading, totalElements, fetchWorkOrders, updateWorkOrderStatus } = useWorkOrderStore();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [editingWorkOrder, setEditingWorkOrder] = useState<any | null>(null);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [assignModalVisible, setAssignModalVisible] = useState(false);
  const [selectedWorkOrderId, setSelectedWorkOrderId] = useState<string | null>(null);
  const [selectedWorkOrder, setSelectedWorkOrder] = useState<any | null>(null);
  
  const userPermsStr = localStorage.getItem('permissions') || '';
  const userPerms = userPermsStr.split(',').map(p => p.trim());
  const isSuperAdmin = userPerms.includes('system:admin');
  const canUpdate = isSuperAdmin || userPerms.includes('work_order:update');
  const canDelete = isSuperAdmin || userPerms.includes('work_order:delete');
  const canAssign = isSuperAdmin || userPerms.includes('work_order:reassign');
  const canCreate = isSuperAdmin || userPerms.includes('work_order:create');
  const [searchText, setSearchText] = useState('');
  const currentUsername = localStorage.getItem('username');

  useEffect(() => {
    fetchWorkOrders(currentPage - 1, pageSize);
  }, [currentPage, pageSize, fetchWorkOrders]);

  const handleUpdateStatus = async (id: string, status: string) => {
    const success = await updateWorkOrderStatus(id, status);
    if (success) {
      message.success(`Đã cập nhật trạng thái thành ${status}`);
      fetchWorkOrders(currentPage - 1, pageSize);
    } else {
      message.error(useWorkOrderStore.getState().error || 'Cập nhật trạng thái thất bại');
    }
  };

  const handleDelete = async (id: string) => {
    const success = await useWorkOrderStore.getState().deleteWorkOrder(id);
    if (success) {
      message.success('Xóa Work Order thành công');
      fetchWorkOrders(currentPage - 1, pageSize);
    } else {
      message.error(useWorkOrderStore.getState().error || 'Xóa Work Order thất bại');
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'CRITICAL': return 'magenta';
      case 'HIGH': return 'red';
      case 'MEDIUM': return 'orange';
      case 'LOW': return 'green';
      default: return 'default';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'CREATED': return 'blue';
      case 'ASSIGNED': return 'cyan';
      case 'IN_PROGRESS': return 'gold';
      case 'COMPLETED': return 'green';
      case 'CANCELED': return 'default';
      default: return 'default';
    }
  };

  const columns = [
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      sorter: (a: any, b: any) => (a.title || '').localeCompare(b.title || ''),
      render: (text: string, record: any) => (
        <div className="flex flex-col items-start">
          <Tooltip title={text}>
            <strong className="text-neutral-800 truncate w-full block max-w-[180px] md:max-w-[250px]">{text}</strong>
          </Tooltip>
          <div className="flex gap-1 mt-1 flex-wrap w-full">
            {record.parentWorkOrder && (
               <Tooltip title={`Kế thừa từ: ${record.parentWorkOrder.title}`}>
                 <Tag color="purple" className="text-[10px] border-0 leading-tight m-0 max-w-[180px] md:max-w-[250px] inline-flex items-center">
                   <span className="truncate">↳ Kế thừa: {record.parentWorkOrder.title}</span>
                 </Tag>
               </Tooltip>
            )}
            {record.followUpWorkOrders && record.followUpWorkOrders.length > 0 && (
               <Tag color="blue" className="text-[10px] border-0 leading-tight m-0 whitespace-nowrap">Có {record.followUpWorkOrders.length} Follow-ups</Tag>
            )}
          </div>
        </div>
      ),
    },
    {
      title: 'Asset',
      dataIndex: ['asset', 'name'],
      key: 'assetName',
      sorter: (a: any, b: any) => (a.asset?.name || '').localeCompare(b.asset?.name || ''),
      render: (text: string) => (
        <Tooltip title={text}>
          <div className="max-w-[150px] truncate text-neutral-600 font-medium">
            {text || '-'}
          </div>
        </Tooltip>
      ),
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      sorter: (a: any, b: any) => (a.priority || '').localeCompare(b.priority || ''),
      filters: [
        { text: 'CRITICAL', value: 'CRITICAL' },
        { text: 'HIGH', value: 'HIGH' },
        { text: 'MEDIUM', value: 'MEDIUM' },
        { text: 'LOW', value: 'LOW' },
      ],
      onFilter: (value: any, record: any) => record.priority === value,
      render: (priority: string) => (
        <Tag color={getPriorityColor(priority)} className="rounded-full px-3 font-bold">{priority}</Tag>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      sorter: (a: any, b: any) => (a.status || '').localeCompare(b.status || ''),
      filters: [
        { text: 'CREATED', value: 'CREATED' },
        { text: 'ASSIGNED', value: 'ASSIGNED' },
        { text: 'IN_PROGRESS', value: 'IN_PROGRESS' },
        { text: 'COMPLETED', value: 'COMPLETED' },
        { text: 'CANCELED', value: 'CANCELED' },
      ],
      onFilter: (value: any, record: any) => record.status === value,
      render: (status: string) => (
        <Tag color={getStatusColor(status)} className="rounded-full px-3 font-bold">{status}</Tag>
      ),
    },
    {
      title: 'Assignee',
      dataIndex: ['assignee', 'username'],
      key: 'assignee',
      render: (username: string) => username || '-',
    },
    {
      title: 'Requested By',
      dataIndex: ['creator', 'username'],
      key: 'creator',
      render: (username: string) => (
        <span>{username || '-'}</span>
      ),
    },
    {
      title: 'Deadline',
      dataIndex: 'deadline',
      key: 'deadline',
      sorter: (a: any, b: any) => new Date(a.deadline || 0).getTime() - new Date(b.deadline || 0).getTime(),
      render: (deadline: string) => deadline ? (
        <span className="text-neutral-600">{dayjs(deadline).format('YYYY-MM-DD HH:mm')}</span>
      ) : '-',
    },
    {
      title: 'Created At',
      dataIndex: 'createdAt',
      key: 'createdAt',
      sorter: (a: any, b: any) => new Date(a.createdAt || 0).getTime() - new Date(b.createdAt || 0).getTime(),
      render: (createdAt: string) => createdAt ? (
        <span className="text-neutral-600">{dayjs(createdAt).format('YYYY-MM-DD HH:mm')}</span>
      ) : '-',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: any) => {
        return (
          <div className="flex gap-2 items-center">
            <Tooltip title="Xem chi tiết">
              <Button
                type="text"
                className="text-neutral-500 hover:text-primary bg-neutral-50 hover:bg-primary-50"
                icon={<EyeOutlined />}
                onClick={() => {
                  setSelectedWorkOrder(record);
                  setDetailDrawerVisible(true);
                }}
              />
            </Tooltip>
            
            {canUpdate && (record.status === 'CREATED' || record.status === 'ASSIGNED') && (
              <Tooltip title="Chỉnh sửa">
                <Button
                  type="text"
                  className="text-neutral-500 hover:text-primary bg-neutral-50 hover:bg-primary-50"
                  icon={<EditOutlined />}
                  onClick={() => {
                    setEditingWorkOrder(record);
                    setDrawerVisible(true);
                  }}
                />
              </Tooltip>
            )}

            {canAssign && record.status !== 'COMPLETED' && record.status !== 'CANCELED' && (
              <Tooltip title={record.assignee ? 'Phân công lại' : 'Phân công'}>
                <Button
                  type="text"
                  className="text-neutral-500 hover:text-primary bg-neutral-50 hover:bg-primary-50"
                  icon={<UserSwitchOutlined />}
                  onClick={() => {
                    setSelectedWorkOrderId(record.id);
                    setSelectedWorkOrder(record);
                    setAssignModalVisible(true);
                  }}
                />
              </Tooltip>
            )}

            {canDelete && (record.status === 'CREATED' || record.status === 'ASSIGNED') && (
              <Popconfirm
                title="Xóa Work Order"
                description={
                  record.followUpWorkOrders && record.followUpWorkOrders.length > 0
                    ? "Work Order này có Follow-up. Bạn phải xóa các Follow-up trước khi xóa Work Order gốc."
                    : "Bạn có chắc chắn muốn xóa Work Order này không?"
                }
                onConfirm={() => handleDelete(record.id)}
                okText="Xóa"
                cancelText="Hủy"
                okButtonProps={{ danger: true, disabled: record.followUpWorkOrders && record.followUpWorkOrders.length > 0 }}
              >
                <Tooltip title="Xóa">
                  <Button
                    type="text"
                    danger
                    className="hover:bg-red-50"
                    icon={<DeleteOutlined />}
                  />
                </Tooltip>
              </Popconfirm>
            )}

            {record.status === 'ASSIGNED' && record.assignee?.username === currentUsername && (
              <Tooltip title="Bắt đầu">
                <Button type="primary" size="small" icon={<PlayCircleOutlined />} className="bg-blue-500" onClick={() => handleUpdateStatus(record.id, 'IN_PROGRESS')} />
              </Tooltip>
            )}
            {record.status === 'IN_PROGRESS' && record.assignee?.username === currentUsername && (
              <Tooltip title={
                record.checklists?.some((c: any) => c.isMandatory && !c.completed) 
                  ? "Chưa hoàn thành các Checklist bắt buộc" 
                  : "Hoàn thành"
              }>
                <Button 
                  type="primary" 
                  size="small" 
                  icon={<CheckCircleOutlined />} 
                  className={record.checklists?.some((c: any) => c.isMandatory && !c.completed) ? "bg-neutral-300" : "bg-green-500 hover:bg-green-600"} 
                  disabled={record.checklists?.some((c: any) => c.isMandatory && !c.completed)}
                  onClick={() => handleUpdateStatus(record.id, 'COMPLETED')} 
                />
              </Tooltip>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="bg-transparent h-full flex flex-col space-y-6">
      {/* Massive Beautiful Header */}
      <div className="bg-white p-6 md:p-8 rounded-3xl border border-neutral-200/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative overflow-hidden shrink-0 group">
        <div className="absolute top-0 right-0 -mr-32 -mt-32 w-[500px] h-[500px] rounded-full bg-gradient-to-bl from-primary-200/40 via-primary-50/20 to-transparent blur-3xl opacity-60 pointer-events-none group-hover:scale-110 transition-transform duration-1000"></div>
        <div className="absolute bottom-0 left-0 -ml-32 -mb-32 w-80 h-80 rounded-full bg-gradient-to-tr from-info/10 to-transparent blur-3xl opacity-50 pointer-events-none"></div>
        
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center text-primary shadow-[inset_0_2px_10px_rgba(255,255,255,1),0_4px_15px_rgba(0,160,226,0.2)] border border-primary/20 transform -rotate-12 group-hover:rotate-12 group-hover:scale-110 transition duration-500">
              <i className="ph-fill ph-clipboard-text text-3xl drop-shadow-sm"></i>
            </div>
            <div>
              <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-neutral-900 via-neutral-700 to-neutral-600 tracking-tight m-0 drop-shadow-sm">
                Work Orders
              </h2>
              <p className="text-neutral-500 text-base font-medium mt-1 mb-0 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                Quản lý, phân công và theo dõi các yêu cầu bảo trì tài sản.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {canCreate && (
              <Button 
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditingWorkOrder(null);
                  setDrawerVisible(true);
                }} 
                className="rounded-xl h-10 px-5 font-bold flex items-center justify-center gap-2 shadow-sm"
              >
                Tạo Work Order
              </Button>
            )}
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
            placeholder="Tìm kiếm Work Order theo tiêu đề..." 
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full sm:max-w-md h-12 rounded-xl border-neutral-200/80 hover:border-primary focus-within:border-primary focus-within:shadow-[0_0_0_3px_rgba(0,160,226,0.15)] bg-neutral-50/50 hover:bg-white focus-within:bg-white transition-all text-base font-medium px-4 shadow-[0_2px_10px_rgba(0,0,0,0.02)]"
          />
          <div className="flex items-center gap-2 text-sm font-bold text-neutral-500 bg-neutral-50/80 px-4 py-2 rounded-lg border border-neutral-100">
             <i className="ph-fill ph-clipboard-text text-primary"></i>
             <span>
                {workOrders.filter(w => (w.title || '').toLowerCase().includes(searchText.toLowerCase())).length} Work Orders
             </span>
          </div>
        </div>

        <div className="p-2 flex-1 flex flex-col overflow-x-auto">
          <Table
            columns={columns}
            dataSource={workOrders.filter(w => (w.title || '').toLowerCase().includes(searchText.toLowerCase()))}
            rowKey="id"
            loading={loading}
            size="middle"
            className="flex-1 custom-beautiful-table min-w-max"
            pagination={{
              current: currentPage,
              pageSize: pageSize,
              total: totalElements,
              showSizeChanger: true,
              className: 'mt-6 px-4 pb-4',
              onChange: (page, size) => {
                setCurrentPage(page);
                setPageSize(size);
              },
            }}
            scroll={{ x: 'max-content' }}
          />
        </div>
      </div>

      <CreateWorkOrderDrawer
        visible={drawerVisible}
        onClose={() => {
          setDrawerVisible(false);
          setEditingWorkOrder(null);
          fetchWorkOrders(currentPage - 1, pageSize);
        }}
        editingWorkOrder={editingWorkOrder}
      />

      {selectedWorkOrderId && (
        <AssignWorkOrderModal
          visible={assignModalVisible}
          onClose={() => setAssignModalVisible(false)}
          workOrderId={selectedWorkOrderId}
          currentAssigneeId={selectedWorkOrder?.assignee?.id}
        />
      )}

      <WorkOrderDetailDrawer
        visible={detailDrawerVisible}
        onClose={() => setDetailDrawerVisible(false)}
        workOrder={workOrders.find(w => w.id === selectedWorkOrder?.id) || selectedWorkOrder}
      />
    </div>
  );
};

export default WorkOrderList;
