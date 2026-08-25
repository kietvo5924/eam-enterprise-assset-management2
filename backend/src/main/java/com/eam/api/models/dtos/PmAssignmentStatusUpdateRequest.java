package com.eam.api.models.dtos;

import com.eam.api.models.enums.PmAssignmentStatus;
import jakarta.validation.constraints.NotNull;

public class PmAssignmentStatusUpdateRequest {
    @NotNull(message = "Status is required")
    private PmAssignmentStatus status;

    public PmAssignmentStatus getStatus() {
        return status;
    }

    public void setStatus(PmAssignmentStatus status) {
        this.status = status;
    }
}
