package com.eam.api.models.events;

import com.eam.api.models.enums.PmTriggerType;
import java.time.ZonedDateTime;
import java.util.UUID;

public class MaintenanceTriggeredEvent {
    private String tenantId;
    private UUID assetId;
    private UUID pmPlanId;
    private PmTriggerType triggerType;
    private String priority;
    private String title;
    private String description;
    private ZonedDateTime dueDate;

    public MaintenanceTriggeredEvent() {}

    public MaintenanceTriggeredEvent(String tenantId, UUID assetId, UUID pmPlanId, PmTriggerType triggerType, String priority, String title, String description, ZonedDateTime dueDate) {
        this.tenantId = tenantId;
        this.assetId = assetId;
        this.pmPlanId = pmPlanId;
        this.triggerType = triggerType;
        this.priority = priority;
        this.title = title;
        this.description = description;
        this.dueDate = dueDate;
    }

    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }

    public UUID getAssetId() { return assetId; }
    public void setAssetId(UUID assetId) { this.assetId = assetId; }

    public UUID getPmPlanId() { return pmPlanId; }
    public void setPmPlanId(UUID pmPlanId) { this.pmPlanId = pmPlanId; }

    public PmTriggerType getTriggerType() { return triggerType; }
    public void setTriggerType(PmTriggerType triggerType) { this.triggerType = triggerType; }

    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public ZonedDateTime getDueDate() { return dueDate; }
    public void setDueDate(ZonedDateTime dueDate) { this.dueDate = dueDate; }
}
