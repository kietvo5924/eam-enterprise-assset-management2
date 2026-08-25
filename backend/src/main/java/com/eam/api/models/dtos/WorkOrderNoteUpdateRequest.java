package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotNull;

public class WorkOrderNoteUpdateRequest {
    @NotNull(message = "Notes cannot be null")
    private String resolutionNotes;

    public String getResolutionNotes() { return resolutionNotes; }
    public void setResolutionNotes(String resolutionNotes) { this.resolutionNotes = resolutionNotes; }
}
