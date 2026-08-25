package com.eam.api.models.dtos;

import java.util.UUID;

public class PmPlanChecklistDto {
    private UUID id;
    private String itemName;
    private String inputType;
    private String expectedValue;
    private Boolean isMandatory;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public String getItemName() { return itemName; }
    public void setItemName(String itemName) { this.itemName = itemName; }
    public String getInputType() { return inputType; }
    public void setInputType(String inputType) { this.inputType = inputType; }
    public String getExpectedValue() { return expectedValue; }
    public void setExpectedValue(String expectedValue) { this.expectedValue = expectedValue; }
    public Boolean getIsMandatory() { return isMandatory; }
    public void setIsMandatory(Boolean isMandatory) { this.isMandatory = isMandatory; }
}
