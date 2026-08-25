package com.eam.api.models.dtos;

import java.math.BigDecimal;
import java.util.UUID;

public class PmPlanMaterialDto {
    private UUID id;
    private UUID sparePartId;
    private String sparePartName;
    private BigDecimal quantity;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public UUID getSparePartId() { return sparePartId; }
    public void setSparePartId(UUID sparePartId) { this.sparePartId = sparePartId; }
    public String getSparePartName() { return sparePartName; }
    public void setSparePartName(String sparePartName) { this.sparePartName = sparePartName; }
    public BigDecimal getQuantity() { return quantity; }
    public void setQuantity(BigDecimal quantity) { this.quantity = quantity; }
}
