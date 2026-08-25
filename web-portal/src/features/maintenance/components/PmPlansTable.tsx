import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Tooltip, Tag, Popconfirm, message, Drawer, List, Modal, Select, Dropdown, Switch } from 'antd';
import { DeleteOutlined, LinkOutlined, EditOutlined, PlusOutlined, PauseCircleOutlined, PlayCircleOutlined, StopOutlined, MoreOutlined } from '@ant-design/icons';
import { usePmPlanStore } from '../store/usePmPlanStore';
import type { PmPlan, PmPlanAssignment } from '../store/usePmPlanStore';
import { CreatePmPlanForm } from './CreatePmPlanForm';
import { AssignPmPlanModal } from './AssignPmPlanModal';
import { useAssetRegistryStore } from '../../assets/store/useAssetRegistryStore';

export const PmPlansTable: React.FC = () => {
  const { pmPlans, isLoading, fetchPmPlans, deletePmPlan, updatePmPlan, fetchAssignments, deleteAssignment, assignPmPlanToAssets, updateAssignmentStatus } = usePmPlanStore();
  const { assets, fetchAssets } = useAssetRegistryStore();
  const [assignmentsVisible, setAssignmentsVisible] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<PmPlan | null>(null);

  const [editModalVisible, setEditModalVisible] = useState(false);
  const [assignModalVisible, setAssignModalVisible] = useState(false);
  const [assignments, setAssignments] = useState<PmPlanAssignment[]>([]);
  const [loadingAssignments, setLoadingAssignments] = useState(false);
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);
  const [isAssigning, setIsAssigning] = useState(false);

  useEffect(() => {
    fetchPmPlans();
    fetchAssets(0, 200);
  }, [fetchPmPlans, fetchAssets]);

  const handleDelete = async (id: string) => {
    try {
      const success = await deletePmPlan(id);
      if (success) {
        message.success('PM Plan deleted successfully');
        fetchPmPlans();
      } else {
        message.error('Failed to delete PM Plan');
      }
    } catch (error: any) {
      message.error(error.message || 'Failed to delete PM Plan');
    }
  };

  const handleToggleActive = async (record: PmPlan, checked: boolean) => {
    try {
      const success = await updatePmPlan(record.id, { isActive: checked });
      if (success) {
        message.success(`Đã ${checked ? 'kích hoạt' : 'vô hiệu hóa'} PM Plan`);
        fetchPmPlans();
      } else {
        message.error('Cập nhật trạng thái thất bại');
      }
    } catch (error) {
      message.error('Cập nhật trạng thái thất bại');
    }
  };

  const handleViewAssignments = async (plan: PmPlan) => {
    setSelectedPlan(plan);
    setAssignmentsVisible(true);
    setLoadingAssignments(true);
    const data = await fetchAssignments(plan.id);
    setAssignments(data);
    setLoadingAssignments(false);
  };

  const handleRemoveAssignment = async (assignmentId: string) => {
    try {
      const success = await deleteAssignment(assignmentId);
      if (success && selectedPlan) {
        message.success('Assignment removed successfully');
        const data = await fetchAssignments(selectedPlan.id);
        setAssignments(data);
      } else {
        message.error('Failed to remove assignment');
      }
    } catch (error: any) {
      message.error(error.message || 'Failed to remove assignment');
    }
  };

  const handleUpdateStatus = async (assignmentId: string, status: 'ACTIVE' | 'PAUSED' | 'DEACTIVATED') => {
    const success = await updateAssignmentStatus(assignmentId, status);
    if (success && selectedPlan) {
      message.success(`Trạng thái đã được cập nhật thành ${status}`);
      const data = await fetchAssignments(selectedPlan.id);
      setAssignments(data);
    } else {
      message.error('Cập nhật trạng thái thất bại');
    }
  };

  const confirmDelete = (assignmentId: string) => {
    Modal.confirm({
      title: 'Xóa hẳn phép gán?',
      content: 'Chỉ dùng khi gán nhầm, chưa có Work Order. Bạn có chắc chắn muốn xóa?',
      okText: 'Xóa',
      okType: 'danger',
      cancelText: 'Hủy',
      onOk: () => handleRemoveAssignment(assignmentId),
    });
  };

  const confirmDeactivate = (assignmentId: string) => {
    Modal.confirm({
      title: 'Vô hiệu hóa tài sản này khỏi plan?',
      content: 'Tài sản sẽ không còn được tự động tạo Work Order mới.',
      okText: 'Đồng ý',
      cancelText: 'Hủy',
      onOk: () => handleUpdateStatus(assignmentId, 'DEACTIVATED'),
    });
  };

  const getDropdownItems = (item: PmPlanAssignment): any[] => [
    item.status === 'ACTIVE' ? {
      key: 'pause',
      label: 'Tạm dừng',
      icon: <PauseCircleOutlined />,
      onClick: () => handleUpdateStatus(item.id, 'PAUSED')
    } : {
      key: 'resume',
      label: 'Kích hoạt lại',
      icon: <PlayCircleOutlined />,
      onClick: () => handleUpdateStatus(item.id, 'ACTIVE')
    },
    {
      key: 'deactivate',
      label: 'Vô hiệu hóa',
      icon: <StopOutlined />,
      onClick: () => confirmDeactivate(item.id)
    },
    {
      type: 'divider'
    },
    {
      key: 'delete',
      danger: true,
      label: 'Xóa hẳn (Hard Delete)',
      icon: <DeleteOutlined />,
      onClick: () => confirmDelete(item.id)
    }
  ];

  const handleAssignAssets = async () => {
    if (!selectedPlan || selectedAssetIds.length === 0) return;
    setIsAssigning(true);
    try {
      const success = await assignPmPlanToAssets(selectedPlan.id, selectedAssetIds);
      if (success) {
        message.success('Đã gán tài sản thành công');
        setSelectedAssetIds([]);
        const data = await fetchAssignments(selectedPlan.id);
        setAssignments(data);
      } else {
        message.error('Có lỗi xảy ra khi gán tài sản');
      }
    } catch (error: any) {
      if (error.response?.data?.message) {
        message.error(error.response.data.message);
      } else {
        message.error('Có lỗi xảy ra khi gán tài sản');
      }
    } finally {
      setIsAssigning(false);
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: PmPlan, b: PmPlan) => a.name.localeCompare(b.name),
      render: (text: string) => <span className="font-semibold text-neutral-800">{text}</span>,
    },
    {
      title: 'Trigger Type',
      dataIndex: 'triggerType',
      key: 'triggerType',
      sorter: (a: PmPlan, b: PmPlan) => a.triggerType.localeCompare(b.triggerType),
      render: (type: string) => (
        <Tag color={type === 'TIME' ? 'blue' : type === 'METER' ? 'purple' : 'orange'}>
          {type}
        </Tag>
      ),
    },
    {
      title: 'Interval',
      key: 'interval',
      render: (_: any, record: PmPlan) => {
        if (!record.intervalValue) return '-';
        return `${record.intervalValue} ${record.intervalUnit || ''}`;
      },
    },
    {
      title: 'Lead Time',
      key: 'leadTimeDays',
      render: (_: any, record: PmPlan) => {
        return record.leadTimeDays ? `${record.leadTimeDays} days` : '-';
      },
    },
    {
      title: 'Duration',
      key: 'estimatedDurationMinutes',
      render: (_: any, record: PmPlan) => {
        return record.estimatedDurationMinutes ? `${record.estimatedDurationMinutes} mins` : '-';
      },
    },
    {
      title: 'Checklists',
      key: 'checklists',
      render: (_: any, record: PmPlan) => {
        return record.checklists?.length || 0;
      },
    },
    {
      title: 'Assignee',
      key: 'assignee',
      render: (_: any, record: PmPlan) => {
        return record.assignee?.fullName || record.assignee?.username || '-';
      },
    },
    {
      title: 'Materials',
      key: 'materials',
      render: (_: any, record: PmPlan) => {
        return record.materials?.length || 0;
      },
    },
    {
      title: 'Status',
      dataIndex: 'isActive',
      key: 'isActive',
      filters: [
        { text: 'Active', value: true },
        { text: 'Inactive', value: false },
      ],
      onFilter: (value: boolean | React.Key, record: PmPlan) => record.isActive === value,
      render: (active: boolean, record: PmPlan) => (
        <Switch 
          checked={active} 
          onChange={(checked) => handleToggleActive(record, checked)} 
          checkedChildren="Active" 
          unCheckedChildren="Inactive" 
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: PmPlan) => (
        <Space size="middle">
          <Tooltip title="Edit Plan">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => {
                setSelectedPlan(record);
                setEditModalVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="View Assignments">
            <Button
              type="text"
              icon={<LinkOutlined />}
              onClick={() => handleViewAssignments(record)}
            />
          </Tooltip>
          <Tooltip title="Delete">
            <Popconfirm
              title="Delete this PM Plan?"
              description="This will also remove all assignments for this plan."
              onConfirm={() => handleDelete(record.id)}
              okText="Yes"
              cancelText="No"
              okButtonProps={{ danger: true }}
            >
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div className="flex flex-col h-full bg-white border border-neutral-200 rounded-3xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] overflow-hidden">
      <div className="p-4 border-b border-neutral-200 bg-white shrink-0">
        <h3 className="font-bold text-lg text-neutral-800 m-0">PM Plans Management</h3>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <Table
          dataSource={pmPlans}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ pageSize: 10 }}
        />
      </div>

      <Drawer
        title={`Assignments for ${selectedPlan?.name}`}
        placement="right"
        onClose={() => setAssignmentsVisible(false)}
        open={assignmentsVisible}
        size="default"
      >
        <div className="mb-4 flex gap-2">
          <Select
            mode="multiple"
            maxTagCount="responsive"
            placeholder="Chọn thêm tài sản..."
            className="flex-1"
            value={selectedAssetIds}
            onChange={setSelectedAssetIds}
            options={assets.map(asset => ({
              label: `${asset.name} - ${asset.qrCode}`,
              value: asset.id,
              disabled: assignments.some(a => a.assetId === asset.id)
            }))}
            showSearch
            filterOption={(input, option) =>
              (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
            }
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleAssignAssets}
            loading={isAssigning}
            disabled={selectedAssetIds.length === 0}
          >
            Thêm
          </Button>
        </div>
        <List
          loading={loadingAssignments}
          itemLayout="horizontal"
          dataSource={assignments}
          locale={{ emptyText: 'No assets assigned to this plan.' }}
          renderItem={item => (
            <List.Item
              actions={[
                <Dropdown menu={{ items: getDropdownItems(item) }} trigger={['click']} placement="bottomRight">
                  <Button type="text" icon={<MoreOutlined />} />
                </Dropdown>
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <span className="font-semibold">{item.assetName}</span>
                    <Tag color={item.status === 'ACTIVE' ? 'green' : item.status === 'PAUSED' ? 'orange' : 'default'}>{item.status}</Tag>
                  </Space>
                }
                description={`Asset ID: ${item.assetId}`}
              />
            </List.Item>
          )}
        />
      </Drawer>

      <Modal
        title="Edit Preventive Maintenance Plan"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        footer={null}
        destroyOnHidden
      >
        <CreatePmPlanForm
          initialData={selectedPlan || undefined}
          onSuccess={() => {
            setEditModalVisible(false);
            fetchPmPlans();
          }}
          onCancel={() => setEditModalVisible(false)}
        />
      </Modal>

      <AssignPmPlanModal
        initialPmPlanId={selectedPlan?.id}
        visible={assignModalVisible}
        onCancel={() => setAssignModalVisible(false)}
        onSuccess={() => {
          setAssignModalVisible(false);
          if (selectedPlan) {
            handleViewAssignments(selectedPlan); // refresh the list
          }
        }}
      />
    </div>
  );
};
