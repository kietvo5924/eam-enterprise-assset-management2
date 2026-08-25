package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotNull;
import java.util.UUID;

public class WorkOrderAssignRequest {

    @NotNull(message = "Assignee ID is required")
    private UUID assigneeId;

    public UUID getAssigneeId() {
        return assigneeId;
    }

    public void setAssigneeId(UUID assigneeId) {
        this.assigneeId = assigneeId;
    }
}
