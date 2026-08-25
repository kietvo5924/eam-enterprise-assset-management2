package com.eam.api.models.dtos;

import java.time.ZonedDateTime;
import java.util.UUID;
import com.eam.api.models.enums.WorkOrderStatus;

public class WorkOrderDto {
    private UUID id;
    private AssetResponse asset;
    private String title;
    private String description;
    private String priority;
    private WorkOrderStatus status;
    private ZonedDateTime deadline;
    private ZonedDateTime createdAt;
    private ZonedDateTime updatedAt;
    private UserDto creator;
    private UserDto assignee;
    private ZonedDateTime assignedAt;
    private ZonedDateTime actualStartTime;
    private ZonedDateTime completedAt;
    private String resolutionNotes;
    private java.util.List<WorkOrderChecklistDto> checklists;
    private java.util.List<WorkOrderAttachmentDto> attachments;
    private WorkOrderReferenceDto parentWorkOrder;
    private java.util.List<WorkOrderReferenceDto> followUpWorkOrders;
    
    private Integer estimatedDurationMinutes;
    private Integer actualDurationMinutes;
    private java.util.List<WorkOrderMaterialDto> materials = new java.util.ArrayList<>();
    // Getters and Setters
    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public AssetResponse getAsset() { return asset; }
    public void setAsset(AssetResponse asset) { this.asset = asset; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }
    public WorkOrderStatus getStatus() { return status; }
    public void setStatus(WorkOrderStatus status) { this.status = status; }
    public ZonedDateTime getDeadline() { return deadline; }
    public void setDeadline(ZonedDateTime deadline) { this.deadline = deadline; }
    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }
    public ZonedDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(ZonedDateTime updatedAt) { this.updatedAt = updatedAt; }
    public UserDto getCreator() { return creator; }
    public void setCreator(UserDto creator) { this.creator = creator; }
    public UserDto getAssignee() { return assignee; }
    public void setAssignee(UserDto assignee) { this.assignee = assignee; }
    public ZonedDateTime getAssignedAt() { return assignedAt; }
    public void setAssignedAt(ZonedDateTime assignedAt) { this.assignedAt = assignedAt; }
    public ZonedDateTime getActualStartTime() { return actualStartTime; }
    public void setActualStartTime(ZonedDateTime actualStartTime) { this.actualStartTime = actualStartTime; }
    public ZonedDateTime getCompletedAt() { return completedAt; }
    public void setCompletedAt(ZonedDateTime completedAt) { this.completedAt = completedAt; }
    public String getResolutionNotes() { return resolutionNotes; }
    public void setResolutionNotes(String resolutionNotes) { this.resolutionNotes = resolutionNotes; }
    public java.util.List<WorkOrderChecklistDto> getChecklists() { return checklists; }
    public void setChecklists(java.util.List<WorkOrderChecklistDto> checklists) { this.checklists = checklists; }
    public java.util.List<WorkOrderAttachmentDto> getAttachments() { return attachments; }
    public void setAttachments(java.util.List<WorkOrderAttachmentDto> attachments) { this.attachments = attachments; }
    public WorkOrderReferenceDto getParentWorkOrder() { return parentWorkOrder; }
    public void setParentWorkOrder(WorkOrderReferenceDto parentWorkOrder) { this.parentWorkOrder = parentWorkOrder; }
    public java.util.List<WorkOrderReferenceDto> getFollowUpWorkOrders() { return followUpWorkOrders; }
    public void setFollowUpWorkOrders(java.util.List<WorkOrderReferenceDto> followUpWorkOrders) { this.followUpWorkOrders = followUpWorkOrders; }

    public Integer getEstimatedDurationMinutes() { return estimatedDurationMinutes; }
    public void setEstimatedDurationMinutes(Integer estimatedDurationMinutes) { this.estimatedDurationMinutes = estimatedDurationMinutes; }

    public Integer getActualDurationMinutes() { return actualDurationMinutes; }
    public void setActualDurationMinutes(Integer actualDurationMinutes) { this.actualDurationMinutes = actualDurationMinutes; }

    public java.util.List<WorkOrderMaterialDto> getMaterials() { return materials; }
    public void setMaterials(java.util.List<WorkOrderMaterialDto> materials) { this.materials = materials; }
}
