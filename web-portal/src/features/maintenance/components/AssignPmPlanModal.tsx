import React, { useEffect, useState } from 'react';
import { Modal, Form, Select, message } from 'antd';
import { usePmPlanStore } from '../store/usePmPlanStore';
import { useAssetRegistryStore } from '../../assets/store/useAssetRegistryStore';

interface AssignPmPlanModalProps {
  initialPmPlanId?: string;
  visible: boolean;
  onCancel: () => void;
  onSuccess: () => void;
}

export const AssignPmPlanModal: React.FC<AssignPmPlanModalProps> = ({
  initialPmPlanId,
  visible,
  onCancel,
  onSuccess,
}) => {
  const [form] = Form.useForm();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [assignedAssetIds, setAssignedAssetIds] = useState<string[]>([]);
  
  const { pmPlans, fetchPmPlans, fetchAssignments } = usePmPlanStore();
  const { assets, fetchAssets } = useAssetRegistryStore();

  const selectedPmPlanId = Form.useWatch('pmPlanId', form);

  useEffect(() => {
    if (selectedPmPlanId) {
      fetchAssignments(selectedPmPlanId).then(data => {
        setAssignedAssetIds(data.map(a => a.assetId));
      });
    } else {
      setAssignedAssetIds([]);
    }
  }, [selectedPmPlanId, fetchAssignments]);

  useEffect(() => {
    if (visible) {
      fetchPmPlans();
      fetchAssets(0, 200); // Fetch a reduced page of assets for performance
      form.resetFields();
      setAssignedAssetIds([]);
      if (initialPmPlanId) {
        form.setFieldsValue({ pmPlanId: initialPmPlanId });
      }
    }
  }, [visible, initialPmPlanId, fetchPmPlans, fetchAssets, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setIsSubmitting(true);
      
      const success = await usePmPlanStore.getState().assignPmPlanToAssets(values.pmPlanId, values.assetIds);
      
      if (success) {
        message.success('Đã gán PM Plan cho các tài sản thành công');
        onSuccess();
      } else {
        message.error('Có lỗi xảy ra khi gán PM Plan');
      }
    } catch (error: any) {
      console.error('Validation or API error:', error);
      if (error.response?.data?.message) {
        message.error(error.response.data.message);
      } else if (!error.errorFields) { // Ignore Ant Design validation errors
        message.error('Có lỗi xảy ra khi gán PM Plan');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      title="Gán Kế Hoạch Bảo Trì Cho Tài Sản"
      open={visible}
      onCancel={onCancel}
      onOk={handleSubmit}
      confirmLoading={isSubmitting}
      destroyOnClose
      okText="Lưu"
      cancelText="Hủy"
    >
      <Form form={form} layout="vertical" className="mt-4">
        <Form.Item
          name="pmPlanId"
          label="Kế hoạch bảo trì (PM Plan)"
          rules={[{ required: true, message: 'Vui lòng chọn PM Plan' }]}
        >
          <Select
            placeholder="Chọn kế hoạch bảo trì"
            options={pmPlans.map(plan => ({
              label: plan.name,
              value: plan.id
            }))}
            showSearch
            filterOption={(input, option) =>
              (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Form.Item
          name="assetIds"
          label="Tài sản"
          rules={[{ required: true, message: 'Vui lòng chọn ít nhất một tài sản' }]}
        >
          <Select
            mode="multiple"
            maxTagCount="responsive"
            placeholder="Chọn các tài sản để gán"
            options={assets.map(asset => ({
              label: `${asset.name} - ${asset.qrCode}`,
              value: asset.id,
              disabled: assignedAssetIds.includes(asset.id)
            }))}
            showSearch
            filterOption={(input, option) =>
              (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
            }
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};
