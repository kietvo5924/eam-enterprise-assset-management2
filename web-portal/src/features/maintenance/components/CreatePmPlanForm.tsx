import React, { useState, useEffect } from 'react';
import { Form, Input, Select, InputNumber, Switch, Button, message, Space, Card } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import api from '../../../utils/axios';
import { usePmPlanStore } from '../store/usePmPlanStore';
import type { PmPlan } from '../store/usePmPlanStore';

const { Option } = Select;

interface CreatePmPlanFormProps {
  initialData?: PmPlan;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const CreatePmPlanForm: React.FC<CreatePmPlanFormProps> = ({ initialData, onSuccess, onCancel }) => {
  const [form] = Form.useForm();
  const createPmPlan = usePmPlanStore((state) => state.createPmPlan);
  const updatePmPlan = usePmPlanStore((state) => state.updatePmPlan);
  const [spareParts, setSpareParts] = useState<{ id: string, name: string, partNumber: string }[]>([]);
  const [technicians, setTechnicians] = useState<any[]>([]);
  const [fetchingUsers, setFetchingUsers] = useState(false);

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
    const fetchTechnicians = async () => {
      setFetchingUsers(true);
      try {
        const response = await api.get('/users', { params: { permissionId: 'work_order:execute', size: 100 } });
        if (response.data.success) {
          setTechnicians(response.data.data.content || []);
        }
      } catch (error) {
        console.error('Failed to fetch technicians:', error);
      } finally {
        setFetchingUsers(false);
      }
    };
    fetchSpareParts();
    fetchTechnicians();
  }, []);

  useEffect(() => {
    if (initialData) {
      form.setFieldsValue({
        ...initialData,
        assigneeId: initialData.assignee?.id || initialData.assigneeId
      });
    } else {
      form.resetFields();
    }
  }, [initialData, form]);

  const triggerType = Form.useWatch('triggerType', form);

  const onFinish = async (values: any) => {
    try {
      let success = false;
      if (initialData?.id) {
        success = await updatePmPlan(initialData.id, values as Partial<PmPlan>);
        if (success) {
          message.success('PM Plan updated successfully');
        }
      } else {
        success = await createPmPlan(values as Partial<PmPlan>);
        if (success) {
          message.success('PM Plan created successfully');
        }
      }

      if (success) {
        form.resetFields();
        onSuccess?.();
      }
    } catch (error: any) {
      message.error(error.response?.data?.error?.message || 'Failed to save PM Plan');
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={onFinish}
      initialValues={initialData || {
        triggerType: 'TIME',
        isActive: true,
        isFloatingSchedule: false,
        suppressIfPending: true,
        leadTimeDays: 0,
      }}
    >
      <Form.Item
        name="name"
        label="Name"
        rules={[{ required: true, message: 'Please enter PM Plan name' }]}
      >
        <Input placeholder="Enter PM Plan name" />
      </Form.Item>

      <Form.Item
        name="description"
        label="Description"
      >
        <Input.TextArea rows={3} placeholder="Enter description" />
      </Form.Item>

      <Form.Item
        name="triggerType"
        label="Trigger Type"
        rules={[{ required: true, message: 'Please select a trigger type' }]}
      >
        <Select>
          <Option value="TIME">Time-based</Option>
          <Option value="USAGE">Usage-based</Option>
          <Option value="METER">Meter-based</Option>
        </Select>
      </Form.Item>

      {triggerType === 'TIME' && (
        <div style={{ display: 'flex', gap: '16px' }}>
          <Form.Item
            name="intervalValue"
            label="Interval Value"
            rules={[{ required: true, message: 'Please enter interval value' }]}
            style={{ flex: 1 }}
          >
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="intervalUnit"
            label="Interval Unit"
            rules={[{ required: true, message: 'Please select interval unit' }]}
            style={{ flex: 1 }}
          >
            <Select>
              <Option value="DAYS">Days</Option>
              <Option value="WEEKS">Weeks</Option>
              <Option value="MONTHS">Months</Option>
              <Option value="YEARS">Years</Option>
            </Select>
          </Form.Item>
        </div>
      )}

      {(triggerType === 'USAGE' || triggerType === 'METER') && (
        <Form.Item
          name="intervalValue"
          label="Threshold Value"
          rules={[{ required: true, message: 'Please enter threshold value' }]}
        >
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>
      )}

      <Form.Item
        name="leadTimeDays"
        label="Lead Time (Days)"
        rules={[{ required: true, message: 'Please enter lead time' }]}
        tooltip="Number of days before the actual due date to generate the Work Order"
      >
        <InputNumber min={0} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item
        name="estimatedDurationMinutes"
        label="Estimated Duration (Minutes)"
        rules={[{ required: true, message: 'Please enter estimated duration' }]}
      >
        <InputNumber min={1} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item
        name="assigneeId"
        label="Default Assignee"
        tooltip="Optional. The selected technician will be automatically assigned to any work orders generated from this plan."
      >
        <Select
          placeholder="Select a default technician"
          loading={fetchingUsers}
          allowClear
          options={technicians.map((tech) => ({
            value: tech.id,
            label: tech.username || tech.email,
          }))}
        />
      </Form.Item>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <Form.Item
          name="isFloatingSchedule"
          label="Floating Schedule"
          valuePropName="checked"
          tooltip="If checked, the next due date is calculated from the completion date of the previous work order, not a rigid schedule."
        >
          <Switch checkedChildren="Yes" unCheckedChildren="No (Fixed)" />
        </Form.Item>

        <Form.Item
          name="suppressIfPending"
          label="Suppress If Pending"
          valuePropName="checked"
          tooltip="If checked, new work orders won't be generated if a previous one is still incomplete."
        >
          <Switch checkedChildren="Yes" unCheckedChildren="No" />
        </Form.Item>

        <Form.Item
          name="isActive"
          label="Status"
          valuePropName="checked"
        >
          <Switch checkedChildren="Active" unCheckedChildren="Inactive" />
        </Form.Item>
      </div>

      <div style={{ marginTop: 24, marginBottom: 16, fontWeight: 'bold' }}>SOP Checklist</div>
      <Form.List name="checklists">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...restField }) => (
              <Card size="small" key={key} style={{ marginBottom: 16 }} extra={<MinusCircleOutlined onClick={() => remove(name)} style={{ color: 'red' }} />}>
                <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                  <Form.Item
                    {...restField}
                    name={[name, 'itemName']}
                    rules={[{ required: true, message: 'Missing item name' }]}
                    style={{ flex: '1 1 300px', marginBottom: 8 }}
                  >
                    <Input placeholder="Checklist Item Name (e.g. Inspect Motor)" />
                  </Form.Item>

                  <Form.Item
                    {...restField}
                    name={[name, 'inputType']}
                    style={{ flex: '0 0 150px', marginBottom: 8 }}
                  >
                    <Select placeholder="Input Type">
                      <Option value="PASS_FAIL">Pass / Fail</Option>
                      <Option value="NUMBER">Number</Option>
                      <Option value="TEXT">Text</Option>
                    </Select>
                  </Form.Item>

                  <Form.Item
                    {...restField}
                    name={[name, 'expectedValue']}
                    style={{ flex: '1 1 200px', marginBottom: 8 }}
                  >
                    <Input placeholder="Expected Value (Optional)" />
                  </Form.Item>

                  <Form.Item
                    {...restField}
                    name={[name, 'isMandatory']}
                    valuePropName="checked"
                    style={{ flex: '0 0 100px', marginBottom: 8 }}
                  >
                    <Switch checkedChildren="Mandatory" unCheckedChildren="Optional" />
                  </Form.Item>
                </div>
              </Card>
            ))}
            <Form.Item>
              <Button type="dashed" onClick={() => add({ inputType: 'PASS_FAIL', isMandatory: false })} block icon={<PlusOutlined />}>
                Add Checklist Item
              </Button>
            </Form.Item>
          </>
        )}
      </Form.List>

      <div style={{ marginTop: 24, marginBottom: 16, fontWeight: 'bold' }}>Estimated Materials (Spare Parts)</div>
      <Form.List name="materials">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...restField }) => (
              <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                <Form.Item
                  {...restField}
                  name={[name, 'sparePartId']}
                  rules={[{ required: true, message: 'Missing part' }]}
                  style={{ width: 300 }}
                >
                  <Select placeholder="Select Spare Part">
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
                  rules={[{ required: true, message: 'Missing quantity' }]}
                >
                  <InputNumber min={0.1} step={0.1} placeholder="Quantity" />
                </Form.Item>

                <MinusCircleOutlined onClick={() => remove(name)} style={{ color: 'red' }} />
              </Space>
            ))}
            <Form.Item>
              <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                Add Material
              </Button>
            </Form.Item>
          </>
        )}
      </Form.List>

      <Form.Item style={{ textAlign: 'right', marginBottom: 0 }}>
        {onCancel && (
          <Button onClick={onCancel} style={{ marginRight: 8 }}>
            Cancel
          </Button>
        )}
        <Button type="primary" htmlType="submit">
          Save
        </Button>
      </Form.Item>
    </Form>
  );
};
