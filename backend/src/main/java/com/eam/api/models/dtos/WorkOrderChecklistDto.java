package com.eam.api.models.dtos;

import java.time.ZonedDateTime;
import java.util.UUID;

public class WorkOrderChecklistDto {
    private UUID id;
    private String itemName;
    private boolean isCompleted;
    private String inputType;
    private String expectedValue;
    private String actualValue;
    private Boolean isMandatory;
    private ZonedDateTime createdAt;
    private ZonedDateTime updatedAt;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }

    public String getItemName() { return itemName; }
    public void setItemName(String itemName) { this.itemName = itemName; }

    public boolean isCompleted() { return isCompleted; }
    public void setCompleted(boolean completed) { isCompleted = completed; }

    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }

    public ZonedDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(ZonedDateTime updatedAt) { this.updatedAt = updatedAt; }

    public String getInputType() { return inputType; }
    public void setInputType(String inputType) { this.inputType = inputType; }
    
    public String getExpectedValue() { return expectedValue; }
    public void setExpectedValue(String expectedValue) { this.expectedValue = expectedValue; }

    public String getActualValue() { return actualValue; }
    public void setActualValue(String actualValue) { this.actualValue = actualValue; }

    public Boolean getIsMandatory() { return isMandatory; }
    public void setIsMandatory(Boolean isMandatory) { this.isMandatory = isMandatory; }
}
