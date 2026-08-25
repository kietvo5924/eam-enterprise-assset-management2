package com.eam.api.models.dtos;

import com.eam.api.models.enums.WorkOrderStatus;
import jakarta.validation.constraints.NotNull;

public class WorkOrderStatusUpdateRequest {

    @NotNull(message = "Status is required")
    private WorkOrderStatus status;

    public WorkOrderStatus getStatus() {
        return status;
    }

    public void setStatus(WorkOrderStatus status) {
        this.status = status;
    }
}
