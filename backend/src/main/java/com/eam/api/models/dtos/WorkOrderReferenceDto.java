package com.eam.api.models.dtos;

import java.util.UUID;
import com.eam.api.models.enums.WorkOrderStatus;

public class WorkOrderReferenceDto {
    private UUID id;
    private String title;
    private WorkOrderStatus status;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public WorkOrderStatus getStatus() { return status; }
    public void setStatus(WorkOrderStatus status) { this.status = status; }
}
