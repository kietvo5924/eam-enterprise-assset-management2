package com.eam.api.models.dtos;

import java.math.BigDecimal;
import com.eam.api.models.enums.PmTriggerType;
import com.eam.api.models.enums.PmIntervalUnit;

public class PmPlanUpdateRequest {
    private String name;
    private String description;
    private PmTriggerType triggerType;
    private BigDecimal intervalValue;
    private PmIntervalUnit intervalUnit;
    
    private Boolean isFloatingSchedule;
    
    private Boolean suppressIfPending;
    
    private Boolean isActive;
    private Integer leadTimeDays;
    private Integer estimatedDurationMinutes;
    private java.util.UUID assigneeId;
    private java.util.List<PmPlanChecklistDto> checklists;
    private java.util.List<PmPlanMaterialDto> materials;

    // Getters and Setters
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    
    public PmTriggerType getTriggerType() { return triggerType; }
    public void setTriggerType(PmTriggerType triggerType) { this.triggerType = triggerType; }
    
    public BigDecimal getIntervalValue() { return intervalValue; }
    public void setIntervalValue(BigDecimal intervalValue) { this.intervalValue = intervalValue; }
    
    public PmIntervalUnit getIntervalUnit() { return intervalUnit; }
    public void setIntervalUnit(PmIntervalUnit intervalUnit) { this.intervalUnit = intervalUnit; }
    
    public Boolean getIsFloatingSchedule() { return isFloatingSchedule; }
    public void setIsFloatingSchedule(Boolean isFloatingSchedule) { this.isFloatingSchedule = isFloatingSchedule; }

    public Boolean getSuppressIfPending() { return suppressIfPending; }
    public void setSuppressIfPending(Boolean suppressIfPending) { this.suppressIfPending = suppressIfPending; }

    public Boolean getIsActive() { return isActive; }
    public void setIsActive(Boolean isActive) { this.isActive = isActive; }
    
    public Integer getLeadTimeDays() { return leadTimeDays; }
    public void setLeadTimeDays(Integer leadTimeDays) { this.leadTimeDays = leadTimeDays; }

    public Integer getEstimatedDurationMinutes() { return estimatedDurationMinutes; }
    public void setEstimatedDurationMinutes(Integer estimatedDurationMinutes) { this.estimatedDurationMinutes = estimatedDurationMinutes; }

    public java.util.UUID getAssigneeId() { return assigneeId; }
    public void setAssigneeId(java.util.UUID assigneeId) { this.assigneeId = assigneeId; }

    public java.util.List<PmPlanChecklistDto> getChecklists() { return checklists; }
    public void setChecklists(java.util.List<PmPlanChecklistDto> checklists) { this.checklists = checklists; }

    public java.util.List<PmPlanMaterialDto> getMaterials() { return materials; }
    public void setMaterials(java.util.List<PmPlanMaterialDto> materials) { this.materials = materials; }
}
