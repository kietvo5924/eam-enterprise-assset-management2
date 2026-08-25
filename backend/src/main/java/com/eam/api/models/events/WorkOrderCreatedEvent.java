package com.eam.api.models.events;

import java.util.UUID;

public class WorkOrderCreatedEvent {
    private String tenantId;
    private UUID workOrderId;
    private UUID assetId;
    private String title;
    private String priority;

    public WorkOrderCreatedEvent() {}

    public WorkOrderCreatedEvent(String tenantId, UUID workOrderId, UUID assetId, String title, String priority) {
        this.tenantId = tenantId;
        this.workOrderId = workOrderId;
        this.assetId = assetId;
        this.title = title;
        this.priority = priority;
    }

    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }

    public UUID getWorkOrderId() { return workOrderId; }
    public void setWorkOrderId(UUID workOrderId) { this.workOrderId = workOrderId; }

    public UUID getAssetId() { return assetId; }
    public void setAssetId(UUID assetId) { this.assetId = assetId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }
}
