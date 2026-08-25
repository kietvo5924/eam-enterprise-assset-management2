import React, { useEffect, useState } from 'react';
import { Modal, Form, Select, message } from 'antd';
import { useWorkOrderStore } from '../store/useWorkOrderStore';
import api from '../../../utils/axios';

interface AssignWorkOrderModalProps {
  visible: boolean;
  onClose: () => void;
  workOrderId: string;
  currentAssigneeId?: string;
}

const AssignWorkOrderModal: React.FC<AssignWorkOrderModalProps> = ({ visible, onClose, workOrderId, currentAssigneeId }) => {
  const [form] = Form.useForm();
  const { assignWorkOrder, loading } = useWorkOrderStore();
  const [technicians, setTechnicians] = useState<any[]>([]);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    if (visible) {
      fetchTechnicians();
    } else {
      form.resetFields();
    }
  }, [visible, form]);

  const fetchTechnicians = async () => {
    setFetching(true);
    try {
      const response = await api.get('/users', { params: { permissionId: 'work_order:execute', size: 100 } });
      if (response.data.success) {
        let fetchedTechs = response.data.data.content || [];
        if (currentAssigneeId) {
          fetchedTechs = fetchedTechs.filter((tech: any) => tech.id !== currentAssigneeId);
        }
        setTechnicians(fetchedTechs);
      }
    } catch (error) {
      message.error('Failed to load technicians');
    } finally {
      setFetching(false);
    }
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      const success = await assignWorkOrder(workOrderId, values.assigneeId);
      if (success) {
        message.success('Work order assigned successfully');
        onClose();
      }
    } catch (error) {
      // Validation failed or API error handled in store
    }
  };

  return (
    <Modal
      title="Assign Work Order"
      open={visible}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={loading}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="assigneeId"
          label="Technician"
          rules={[{ required: true, message: 'Please select a technician' }]}
        >
          <Select
            placeholder="Select a technician"
            loading={fetching}
            options={technicians.map((tech) => ({
              value: tech.id,
              label: tech.username || tech.email,
            }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default AssignWorkOrderModal;
