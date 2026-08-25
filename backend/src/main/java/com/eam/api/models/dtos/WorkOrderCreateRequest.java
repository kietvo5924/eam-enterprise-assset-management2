package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import jakarta.validation.constraints.FutureOrPresent;

import java.time.ZonedDateTime;
import java.util.UUID;

public class WorkOrderCreateRequest {

    @NotNull(message = "Asset ID is required")
    private UUID assetId;

    @NotBlank(message = "Title is required")
    @Size(max = 255, message = "Title must not exceed 255 characters")
    private String title;

    private String description;

    @NotBlank(message = "Priority is required")
    @Size(max = 50)
    private String priority;

    @NotNull(message = "Deadline is required")
    @FutureOrPresent(message = "Deadline must be in the present or future")
    private ZonedDateTime deadline;

    private UUID parentWorkOrderId;

    private Integer estimatedDurationMinutes;
    private java.util.List<PmPlanChecklistDto> checklists = new java.util.ArrayList<>();
    private java.util.List<PmPlanMaterialDto> materials = new java.util.ArrayList<>();

    // Getters and Setters
    public UUID getAssetId() { return assetId; }
    public void setAssetId(UUID assetId) { this.assetId = assetId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }
    public ZonedDateTime getDeadline() { return deadline; }
    public void setDeadline(ZonedDateTime deadline) { this.deadline = deadline; }
    public UUID getParentWorkOrderId() { return parentWorkOrderId; }
    public void setParentWorkOrderId(UUID parentWorkOrderId) { this.parentWorkOrderId = parentWorkOrderId; }

    public Integer getEstimatedDurationMinutes() { return estimatedDurationMinutes; }
    public void setEstimatedDurationMinutes(Integer estimatedDurationMinutes) { this.estimatedDurationMinutes = estimatedDurationMinutes; }

    public java.util.List<PmPlanChecklistDto> getChecklists() { return checklists; }
    public void setChecklists(java.util.List<PmPlanChecklistDto> checklists) { this.checklists = checklists; }

    public java.util.List<PmPlanMaterialDto> getMaterials() { return materials; }
    public void setMaterials(java.util.List<PmPlanMaterialDto> materials) { this.materials = materials; }
}
