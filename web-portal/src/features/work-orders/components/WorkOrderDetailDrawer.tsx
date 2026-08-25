import React, { useState } from 'react';
import { Drawer, Button, Input, Checkbox, Upload, message, Typography, Tag, Popconfirm, InputNumber } from 'antd';
import { UploadOutlined, PlusOutlined, CheckCircleOutlined, DeleteOutlined, FileImageOutlined } from '@ant-design/icons';
import { useWorkOrderStore, type WorkOrder } from '../store/useWorkOrderStore';
import dayjs from 'dayjs';
import CreateWorkOrderDrawer from './CreateWorkOrderDrawer';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface WorkOrderDetailDrawerProps {
  visible: boolean;
  onClose: () => void;
  workOrder: WorkOrder | null;
}

const WorkOrderDetailDrawer: React.FC<WorkOrderDetailDrawerProps> = ({ visible, onClose, workOrder }) => {
  const { updateChecklist, deleteChecklist, updateNotes, uploadAttachment, deleteAttachment, fetchWorkOrders } = useWorkOrderStore();

  const [newItemName, setNewItemName] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [createFollowUpVisible, setCreateFollowUpVisible] = useState(false);

  React.useEffect(() => {
    if (workOrder) {
      setNotes(workOrder.resolutionNotes || '');
    }
  }, [workOrder]);

  if (!workOrder) return null;

  const currentUsername = localStorage.getItem('username');
  const isAssignee = workOrder.assignee?.username === currentUsername;
  const userPermsStr = localStorage.getItem('permissions') || '';
  const userPerms = userPermsStr.split(',').map(p => p.trim());
  const isSuperAdmin = userPerms.includes('system:admin'); 
  const canUpdateWO = isSuperAdmin || userPerms.includes('work_order:update');
  const canCreateFollowUp = isSuperAdmin || userPerms.includes('work_order:create');
  
  const canEdit = (isAssignee || canUpdateWO) && (workOrder.status !== 'COMPLETED' && workOrder.status !== 'CANCELED');
  const canEditChecklist = isAssignee && (workOrder.status !== 'COMPLETED' && workOrder.status !== 'CANCELED');

  const handleAddChecklist = async () => {
    if (!newItemName.trim()) return;
    setLoading(true);
    const success = await updateChecklist(workOrder.id, newItemName, false);
    if (success) {
      message.success('Thêm checklist thành công');
      setNewItemName('');
      fetchWorkOrders(); // Refresh to get new checklist
    } else {
      message.error(useWorkOrderStore.getState().error || 'Thêm checklist thất bại');
    }
    setLoading(false);
  };

  const handleToggleChecklist = async (itemName: string, checked: boolean, actualValue?: string) => {
    const success = await updateChecklist(workOrder.id, itemName, checked, actualValue);
    if (success) {
      fetchWorkOrders();
    } else {
      message.error(useWorkOrderStore.getState().error || 'Cập nhật checklist thất bại');
    }
  };

  const handleDeleteChecklist = async (checklistId: string) => {
    const success = await deleteChecklist(workOrder.id, checklistId);
    if (success) {
      message.success('Xóa checklist thành công');
      fetchWorkOrders();
    } else {
      message.error(useWorkOrderStore.getState().error || 'Xóa checklist thất bại');
    }
  };

  const handleUpdateNotes = async () => {
    setLoading(true);
    const success = await updateNotes(workOrder.id, notes);
    if (success) {
      message.success('Cập nhật ghi chú thành công');
      fetchWorkOrders();
    } else {
      message.error(useWorkOrderStore.getState().error || 'Cập nhật ghi chú thất bại');
    }
    setLoading(false);
  };

  const handleUpload = async (file: File) => {
    setLoading(true);
    const success = await uploadAttachment(workOrder.id, file);
    if (success) {
      message.success('Tải ảnh lên thành công');
      fetchWorkOrders();
    } else {
      message.error(useWorkOrderStore.getState().error || 'Tải ảnh lên thất bại');
    }
    setLoading(false);
    return false; // Prevent default upload behavior
  };

  const handleDeleteAttachment = async (attachmentId: string) => {
    const success = await deleteAttachment(workOrder.id, attachmentId);
    if (success) {
      message.success('Xóa hình ảnh thành công');
      fetchWorkOrders();
    } else {
      message.error(useWorkOrderStore.getState().error || 'Xóa hình ảnh thất bại');
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
      case 'CREATED': return 'default';
      case 'ASSIGNED': return 'cyan';
      case 'IN_PROGRESS': return 'blue';
      case 'COMPLETED': return 'green';
      case 'CANCELED': return 'red';
      default: return 'default';
    }
  };

  return (
    <Drawer
      title={<span className="text-xl font-bold">Chi tiết Work Order: {workOrder.title}</span>}
      placement="right"
      size="large"
      onClose={onClose}
      open={visible}
      className="custom-drawer bg-neutral-50"
      extra={
        workOrder.status === 'COMPLETED' && canCreateFollowUp && (
          <Button type="primary" onClick={() => setCreateFollowUpVisible(true)}>
            Tạo Follow-up
          </Button>
        )
      }
    >
      <div className="space-y-6">
        <div className="bg-white p-5 rounded-xl border border-neutral-200 shadow-sm">
          <Title level={5} className="!mt-0 !mb-4 flex items-center gap-2">
            Thông tin chung
          </Title>
          <div className="grid grid-cols-2 gap-y-4 gap-x-6 text-sm">
            <div>
              <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Trạng thái</Text>
              <div><Tag color={getStatusColor(workOrder.status)} className="m-0 font-medium px-2 py-0.5">{workOrder.status}</Tag></div>
            </div>
            <div>
              <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Mức độ</Text>
              <div><Tag color={getPriorityColor(workOrder.priority)} className="m-0 font-medium px-2 py-0.5">{workOrder.priority}</Tag></div>
            </div>
            <div>
              <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Tài sản</Text>
              <div className="font-medium text-neutral-800">{workOrder.asset?.name || '-'}</div>
            </div>
            <div>
              <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Hạn chót</Text>
              <div className="font-medium text-neutral-800">{dayjs(workOrder.deadline).format('DD/MM/YYYY HH:mm')}</div>
            </div>
            <div>
              <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Người thực hiện</Text>
              <div className="font-medium text-neutral-800">{workOrder.assignee?.fullName || workOrder.assignee?.username || 'Chưa phân công'}</div>
            </div>
            <div>
              <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Thời gian dự kiến</Text>
              <div className="font-medium text-neutral-800">{workOrder.estimatedDurationMinutes ? `${workOrder.estimatedDurationMinutes} phút` : '-'}</div>
            </div>
            {workOrder.parentWorkOrder && (
              <div className="col-span-2">
                <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Work Order Gốc</Text>
                <div className="font-medium text-blue-600">
                  <Tag color="processing" className="mr-2">{workOrder.parentWorkOrder.status}</Tag>
                  {workOrder.parentWorkOrder.title} 
                  <span className="text-neutral-400 text-xs ml-2">({workOrder.parentWorkOrder.id.split('-')[0]})</span>
                </div>
              </div>
            )}
            {workOrder.followUpWorkOrders && workOrder.followUpWorkOrders.length > 0 && (
              <div className="col-span-2">
                <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Follow-up Work Orders</Text>
                <div className="font-medium text-neutral-800 space-y-2 mt-1">
                  {workOrder.followUpWorkOrders.map(fw => (
                    <div key={fw.id} className="text-blue-600 flex items-center">
                      <Tag color="processing" className="mr-2">{fw.status}</Tag>
                      <span>{fw.title}</span>
                      <span className="text-neutral-400 text-xs ml-2">({fw.id.split('-')[0]})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="col-span-2">
              <Text type="secondary" className="block mb-1 text-xs uppercase tracking-wider">Mô tả</Text>
              <div className="text-neutral-700 bg-neutral-50 p-3 rounded-lg border border-neutral-100">{workOrder.description || 'Không có mô tả'}</div>
            </div>
          </div>
        </div>

        {workOrder.materials && workOrder.materials.length > 0 && (
          <div className="bg-white p-5 rounded-xl border border-neutral-200 shadow-sm">
            <Title level={5} className="!mt-0 !mb-4 flex items-center gap-2">
              Vật tư & Linh kiện dự trù
            </Title>
            <div className="space-y-2">
              {workOrder.materials.map((mat: any) => (
                <div key={mat.id} className="flex justify-between items-center p-3 bg-neutral-50 rounded-lg border border-neutral-100">
                  <div>
                    <div className="font-medium text-neutral-800">{mat.sparePart?.name}</div>
                    <div className="text-xs text-neutral-500">Mã: {mat.sparePart?.partNumber}</div>
                  </div>
                  <div className="font-bold text-blue-600 bg-blue-50 px-3 py-1 rounded-full text-sm border border-blue-100">
                    SL: {mat.quantity}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="bg-white p-5 rounded-xl border border-neutral-200 shadow-sm">
          <Title level={5} className="!mt-0 !mb-4">Checklist Công Việc</Title>
          <div className="space-y-2 mb-4">
            {workOrder.checklists?.length === 0 && (
              <div className="text-neutral-400 text-sm italic py-2">Chưa có checklist nào.</div>
            )}
            {workOrder.checklists?.map((item) => (
              <div key={item.id} className="flex items-center justify-between group p-2 hover:bg-neutral-50 rounded-lg border border-transparent hover:border-neutral-200 transition-all">
                <div className="flex-1 flex flex-col gap-2">
                  <Checkbox
                    checked={item.completed}
                    onChange={(e) => handleToggleChecklist(item.itemName, e.target.checked, item.actualValue)}
                    disabled={!canEditChecklist}
                  >
                    <span className={`ml-2 ${item.completed ? 'line-through text-neutral-400' : 'text-neutral-800 font-medium'}`}>
                      {item.itemName}
                      {item.expectedValue && <span className="text-neutral-500 font-normal text-xs ml-1">(Yêu cầu: {item.expectedValue})</span>}
                    </span>
                    {item.isMandatory && (
                      <Tag color="red" className="ml-2 text-[10px] px-1 py-0 border-0 leading-tight">Bắt buộc</Tag>
                    )}
                  </Checkbox>
                  {item.inputType === 'NUMBER' && (
                    <InputNumber
                      key={`num-${item.id}-${item.actualValue}`}
                      defaultValue={item.actualValue ? Number(item.actualValue) : undefined}
                      onBlur={(e) => handleToggleChecklist(item.itemName, !!e.target.value || item.completed, e.target.value)}
                      disabled={!canEditChecklist}
                      placeholder="Nhập số liệu..."
                      className="ml-6 w-48"
                    />
                  )}
                  {item.inputType === 'TEXT' && (
                    <Input
                      key={`text-${item.id}-${item.actualValue}`}
                      defaultValue={item.actualValue}
                      onBlur={(e) => handleToggleChecklist(item.itemName, !!e.target.value || item.completed, e.target.value)}
                      disabled={!canEditChecklist}
                      placeholder="Nhập ghi chú..."
                      className="ml-6 w-full max-w-sm"
                    />
                  )}
                </div>
                {(canUpdateWO || (canEdit && !item.isMandatory)) && (
                  <Popconfirm
                    title="Xóa hạng mục này?"
                    onConfirm={() => handleDeleteChecklist(item.id)}
                    okText="Xóa"
                    cancelText="Hủy"
                    okButtonProps={{ danger: true }}
                  >
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      size="small"
                    />
                  </Popconfirm>
                )}
              </div>
            ))}
          </div>

          {canEdit && (
            <div className="flex gap-2 pt-2 border-t border-neutral-100">
              <Input
                placeholder="Thêm hạng mục công việc..."
                value={newItemName}
                onChange={(e) => setNewItemName(e.target.value)}
                onPressEnter={handleAddChecklist}
                className="rounded-lg"
              />
              <Button type="primary" onClick={handleAddChecklist} loading={loading} icon={<PlusOutlined />} className="rounded-lg">
                Thêm
              </Button>
            </div>
          )}
        </div>

        <div className="bg-white p-5 rounded-xl border border-neutral-200 shadow-sm">
          <Title level={5} className="!mt-0 !mb-4 flex items-center justify-between">
            <span>Hình ảnh đính kèm</span>
            {canEdit && (
              <Upload
                accept="image/*"
                beforeUpload={handleUpload}
                showUploadList={false}
              >
                <Button type="dashed" size="small" icon={<UploadOutlined />} loading={loading} className="rounded-md">
                  Tải ảnh (Max 5MB)
                </Button>
              </Upload>
            )}
          </Title>

          {workOrder.attachments?.length === 0 && (
            <div className="flex flex-col items-center justify-center py-6 text-neutral-400 bg-neutral-50 rounded-lg border border-dashed border-neutral-200">
              <FileImageOutlined className="text-3xl mb-2 opacity-50" />
              <span className="text-sm">Chưa có hình ảnh nào</span>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {workOrder.attachments?.map((att) => {
              const minioUrl = import.meta.env.VITE_MINIO_URL || 'http://localhost:9000';
              return (
                <div key={att.id} className="relative aspect-square border border-neutral-200 rounded-xl overflow-hidden group bg-neutral-100 shadow-sm hover:shadow-md transition-all">
                  <img src={`${minioUrl}${att.fileUrl}`} alt={att.fileName} className="w-full h-full object-cover transition-transform group-hover:scale-105" />

                  {canEdit && (
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                      <Popconfirm
                        title="Xóa hình ảnh này?"
                        onConfirm={() => handleDeleteAttachment(att.id)}
                        okText="Xóa"
                        cancelText="Hủy"
                        okButtonProps={{ danger: true }}
                      >
                        <Button type="primary" danger shape="circle" icon={<DeleteOutlined />} size="large" className="shadow-lg" />
                      </Popconfirm>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-neutral-200 shadow-sm">
          <Title level={5} className="!mt-0 !mb-4">Ghi chú / Kết quả</Title>
          <TextArea
            rows={4}
            placeholder="Nhập chi tiết về kết quả sửa chữa, các vấn đề phát sinh hoặc linh kiện đã thay thế..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            disabled={!canEdit}
            className="rounded-lg mb-3"
          />
          {canEdit && (
            <div className="flex justify-end">
              <Button
                type="primary"
                className="bg-green-500 hover:bg-green-600 rounded-lg px-6 font-medium"
                icon={<CheckCircleOutlined />}
                onClick={handleUpdateNotes}
                loading={loading}
              >
                Lưu Ghi Chú
              </Button>
            </div>
          )}
        </div>
      </div>

      <CreateWorkOrderDrawer
        visible={createFollowUpVisible}
        onClose={() => {
          setCreateFollowUpVisible(false);
          fetchWorkOrders(); // refresh the list to see new WO
        }}
        initialAssetId={workOrder.asset?.id}
        initialParentWorkOrderId={workOrder.id}
        initialDescription={`Follow up cho Work Order: ${workOrder.title}`}
      />
    </Drawer>
  );
};

export default WorkOrderDetailDrawer;
