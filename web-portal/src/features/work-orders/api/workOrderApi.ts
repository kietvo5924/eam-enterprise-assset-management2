import api from '../../../utils/axios';

export interface WorkOrderCreateRequest {
  assetId: string;
  title: string;
  description?: string;
  priority: string;
  deadline: string;
  parentWorkOrderId?: string;
  estimatedDurationMinutes?: number;
  checklists?: {
    itemName: string;
    inputType: string;
    expectedValue?: string;
    isMandatory: boolean;
  }[];
  materials?: {
    sparePartId: string;
    quantity: number;
  }[];
}

export const workOrderApi = {
  getWorkOrders: (page = 0, size = 20) => api.get('/work-orders', { params: { page, size } }),
  getWorkOrderKpis: () => api.get('/work-orders/kpis'),
  getWorkOrder: (id: string) => api.get(`/work-orders/${id}`),
  getCalendarEvents: (startDate: string, endDate: string, assetId?: string, categoryId?: string, status?: string) => 
    api.get('/work-orders/calendar', { params: { startDate, endDate, assetId, categoryId, status } }),
  createWorkOrder: (data: WorkOrderCreateRequest) => api.post('/work-orders', data),
  updateWorkOrder: (id: string, data: WorkOrderCreateRequest) => api.put(`/work-orders/${id}`, data),
  deleteWorkOrder: (id: string) => api.delete(`/work-orders/${id}`),
  assignWorkOrder: (id: string, assigneeId: string) => api.put(`/work-orders/${id}/assign`, { assigneeId }),
  updateWorkOrderStatus: (id: string, status: string) => api.put(`/work-orders/${id}/status`, { status }),
  updateChecklist: (id: string, itemName: string, isCompleted: boolean, actualValue?: string) => 
    api.post(`/work-orders/${id}/checklists`, { itemName, isCompleted, actualValue }),
  updateNotes: (id: string, resolutionNotes: string) => 
    api.put(`/work-orders/${id}/notes`, { resolutionNotes }),
  uploadAttachment: (id: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/work-orders/${id}/attachments`, formData);
  },
  deleteChecklist: (id: string, checklistId: string) =>
    api.delete(`/work-orders/${id}/checklists/${checklistId}`),
  deleteAttachment: (id: string, attachmentId: string) =>
    api.delete(`/work-orders/${id}/attachments/${attachmentId}`),
};
