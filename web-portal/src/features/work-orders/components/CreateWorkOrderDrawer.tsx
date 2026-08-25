import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Select, DatePicker, Button, message, InputNumber, Switch, Card, Space } from 'antd';
import { useWorkOrderStore } from '../store/useWorkOrderStore';
import api from '../../../utils/axios';
import dayjs from 'dayjs';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Option } = Select;

interface CreateWorkOrderDrawerProps {
  visible: boolean;
  onClose: () => void;
  initialAssetId?: string;
  initialParentWorkOrderId?: string;
  initialDescription?: string;
  editingWorkOrder?: any;
}

const CreateWorkOrderDrawer: React.FC<CreateWorkOrderDrawerProps> = ({ visible, onClose, initialAssetId, initialParentWorkOrderId, initialDescription, editingWorkOrder }) => {
  const [form] = Form.useForm();
  const { createWorkOrder, updateWorkOrder } = useWorkOrderStore();
  const [loading, setLoading] = useState(false);
  const [assets, setAssets] = useState<any[]>([]);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [spareParts, setSpareParts] = useState<{id: string, name: string, partNumber: string}[]>([]);

  useEffect(() => {
    const fetchSpareParts = async () => {
      try {
        const response = await api.get('/spare-parts');
        if (response.data.success) {
          setSpareParts(response.data.data);
        }
      } catch (error) {
        console.error('Failed to fetch spare parts:', error);
      }
    };
    fetchSpareParts();
  }, []);

  useEffect(() => {
    if (visible) {
      fetchAssets();
      if (editingWorkOrder) {
        form.setFieldsValue({
          assetId: editingWorkOrder.asset?.id,
          title: editingWorkOrder.title,
          description: editingWorkOrder.description,
          priority: editingWorkOrder.priority,
          deadline: editingWorkOrder.deadline ? dayjs(editingWorkOrder.deadline) : undefined,
          parentWorkOrderId: editingWorkOrder.parentWorkOrder?.id,
          estimatedDurationMinutes: editingWorkOrder.estimatedDurationMinutes,
          checklists: editingWorkOrder.checklists?.map((c: any) => ({
            itemName: c.itemName,
            inputType: c.inputType || 'PASS_FAIL',
            expectedValue: c.expectedValue,
            isMandatory: c.isMandatory
          })) || [],
          materials: editingWorkOrder.materials?.map((m: any) => ({
            sparePartId: m.sparePart?.id,
            quantity: m.quantity
          })) || []
        });
      } else if (initialAssetId || initialParentWorkOrderId || initialDescription) {
        form.setFieldsValue({ 
          assetId: initialAssetId, 
          parentWorkOrderId: initialParentWorkOrderId,
          description: initialDescription
        });
      } else {
        form.resetFields();
      }
    }
  }, [visible, initialAssetId, initialParentWorkOrderId, initialDescription, editingWorkOrder, form]);

  const fetchAssets = async () => {
    setLoadingAssets(true);
    try {
      const response = await api.get('/assets', { params: { page: 0, size: 1000 } });
      if (response.data.success) {
        setAssets(response.data.data?.content || []);
      }
    } catch (error) {
      message.error('Failed to load assets');
    } finally {
      setLoadingAssets(false);
    }
  };

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const payload = {
        ...values,
        deadline: values.deadline ? values.deadline.toISOString() : undefined,
        parentWorkOrderId: values.parentWorkOrderId || initialParentWorkOrderId || undefined,
      };
      
      let success = false;
      if (editingWorkOrder) {
        success = await updateWorkOrder(editingWorkOrder.id, payload);
      } else {
        success = await createWorkOrder(payload);
      }
      
      if (success) {
        message.success(editingWorkOrder ? 'Cập nhật Work Order thành công' : 'Tạo Work Order thành công');
        form.resetFields();
        onClose();
      } else {
        message.error(useWorkOrderStore.getState().error || (editingWorkOrder ? 'Cập nhật thất bại' : 'Tạo thất bại'));
      }
    } catch (error) {
      message.error('Failed to process Work Order');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={<span className="font-black text-xl text-neutral-800">{editingWorkOrder ? 'Cập nhật Work Order' : 'Tạo Mới Work Order'}</span>}
      width={600}
      onCancel={onClose}
      open={visible}
      destroyOnHidden
      className="rounded-[24px] overflow-hidden fancy-modal"
      footer={[
        <Button key="back" onClick={onClose} className="rounded-xl h-10 px-6 font-bold">
          Hủy
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={() => form.submit()} className="rounded-xl h-10 px-8 bg-primary font-bold">
          Lưu
        </Button>
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        requiredMark={true}
      >
        <Form.Item name="parentWorkOrderId" hidden>
          <Input />
        </Form.Item>
        <Form.Item
          name="assetId"
          label="Tài sản"
          rules={[{ required: true, message: 'Vui lòng chọn tài sản' }]}
        >
          <Select
            showSearch
            placeholder="Chọn tài sản"
            loading={loadingAssets}
            filterOption={(input, option) =>
              (option?.children as unknown as string).toLowerCase().includes(input.toLowerCase())
            }
          >
            {assets.map((asset) => (
              <Option key={asset.id} value={asset.id}>
                {asset.name} ({asset.qrCode || asset.serialNumber})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          name="title"
          label="Tiêu đề"
          rules={[{ required: true, message: 'Vui lòng nhập tiêu đề' }]}
        >
          <Input placeholder="Nhập tiêu đề công việc" />
        </Form.Item>

        <Form.Item
          name="description"
          label="Mô tả"
        >
          <TextArea rows={4} placeholder="Nhập chi tiết vấn đề" />
        </Form.Item>

        <Form.Item
          name="priority"
          label="Mức độ ưu tiên"
          rules={[{ required: true, message: 'Vui lòng chọn mức độ ưu tiên' }]}
        >
          <Select placeholder="Chọn mức độ">
            <Option value="LOW">Low</Option>
            <Option value="MEDIUM">Medium</Option>
            <Option value="HIGH">High</Option>
            <Option value="CRITICAL">Critical</Option>
          </Select>
        </Form.Item>

        <Form.Item
          name="deadline"
          label="Hạn chót"
          rules={[{ required: true, message: 'Vui lòng chọn hạn chót' }]}
        >
          <DatePicker 
            showTime 
            style={{ width: '100%' }} 
            format="YYYY-MM-DD HH:mm:ss" 
            disabledDate={(current) => current && current < dayjs().startOf('day')}
          />
        </Form.Item>

        <Form.Item
          name="estimatedDurationMinutes"
          label="Thời gian dự kiến (Phút)"
        >
          <InputNumber min={1} style={{ width: '100%' }} placeholder="Nhập thời gian dự kiến (phút)" />
        </Form.Item>

        <div className="font-bold mb-4 mt-6">SOP Checklist (Quy trình chuẩn)</div>
        <Form.List name="checklists">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Card size="small" key={key} className="mb-4 bg-neutral-50/50" extra={<MinusCircleOutlined onClick={() => remove(name)} style={{ color: 'red' }} />}>
                  <div className="flex flex-wrap gap-4">
                    <Form.Item
                      {...restField}
                      name={[name, 'itemName']}
                      rules={[{ required: true, message: 'Nhập tên công việc' }]}
                      className="flex-[1_1_300px] mb-2"
                    >
                      <Input placeholder="Tên công việc (VD: Kiểm tra động cơ)" />
                    </Form.Item>

                    <Form.Item
                      {...restField}
                      name={[name, 'inputType']}
                      className="flex-[0_0_150px] mb-2"
                    >
                      <Select placeholder="Loại dữ liệu">
                        <Option value="PASS_FAIL">Đạt / Không đạt</Option>
                        <Option value="NUMBER">Số liệu</Option>
                        <Option value="TEXT">Văn bản</Option>
                      </Select>
                    </Form.Item>

                    <Form.Item
                      {...restField}
                      name={[name, 'expectedValue']}
                      className="flex-[1_1_200px] mb-2"
                    >
                      <Input placeholder="Giá trị tiêu chuẩn (Không bắt buộc)" />
                    </Form.Item>

                    <Form.Item
                      {...restField}
                      name={[name, 'isMandatory']}
                      valuePropName="checked"
                      className="flex-[0_0_100px] mb-2"
                    >
                      <Switch checkedChildren="Bắt buộc" unCheckedChildren="Tuỳ chọn" />
                    </Form.Item>
                  </div>
                </Card>
              ))}
              <Form.Item>
                <Button type="dashed" onClick={() => add({ inputType: 'PASS_FAIL', isMandatory: false })} block icon={<PlusOutlined />}>
                  Thêm công việc
                </Button>
              </Form.Item>
            </>
          )}
        </Form.List>

        <div className="font-bold mb-4 mt-6">Dự trù Vật tư & Linh kiện</div>
        <Form.List name="materials">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                  <Form.Item
                    {...restField}
                    name={[name, 'sparePartId']}
                    rules={[{ required: true, message: 'Chọn linh kiện' }]}
                    style={{ width: 300 }}
                  >
                    <Select placeholder="Chọn linh kiện/vật tư">
                      {spareParts.map(part => (
                        <Option key={part.id} value={part.id}>
                          {part.name} ({part.partNumber})
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Form.Item
                    {...restField}
                    name={[name, 'quantity']}
                    rules={[{ required: true, message: 'Nhập số lượng' }]}
                  >
                    <InputNumber min={0.1} step={0.1} placeholder="Số lượng" />
                  </Form.Item>

                  <MinusCircleOutlined onClick={() => remove(name)} style={{ color: 'red' }} />
                </Space>
              ))}
              <Form.Item>
                <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                  Thêm vật tư
                </Button>
              </Form.Item>
            </>
          )}
        </Form.List>
      </Form>
    </Modal>
  );
};

export default CreateWorkOrderDrawer;


