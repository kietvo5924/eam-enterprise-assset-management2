package com.eam.api.models.dtos;

import java.util.UUID;
import java.math.BigDecimal;

public class PmPlanAssignmentDto {
    private UUID id;
    private UUID pmPlanId;
    private UUID assetId;
    private String assetName;
    private BigDecimal baselineMeterReading;
    private com.eam.api.models.enums.PmAssignmentStatus status;
    
    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    
    public UUID getPmPlanId() { return pmPlanId; }
    public void setPmPlanId(UUID pmPlanId) { this.pmPlanId = pmPlanId; }
    
    public UUID getAssetId() { return assetId; }
    public void setAssetId(UUID assetId) { this.assetId = assetId; }
    
    public String getAssetName() { return assetName; }
    public void setAssetName(String assetName) { this.assetName = assetName; }
    
    public BigDecimal getBaselineMeterReading() { return baselineMeterReading; }
    public void setBaselineMeterReading(BigDecimal baselineMeterReading) { this.baselineMeterReading = baselineMeterReading; }

    public com.eam.api.models.enums.PmAssignmentStatus getStatus() { return status; }
    public void setStatus(com.eam.api.models.enums.PmAssignmentStatus status) { this.status = status; }
}
