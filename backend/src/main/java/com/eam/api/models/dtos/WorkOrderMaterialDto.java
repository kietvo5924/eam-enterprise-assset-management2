package com.eam.api.models.dtos;

import java.math.BigDecimal;
import java.util.UUID;

public class WorkOrderMaterialDto {
    private UUID id;
    private SparePartDto sparePart;
    private BigDecimal quantity;
    private BigDecimal actualCost;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public SparePartDto getSparePart() { return sparePart; }
    public void setSparePart(SparePartDto sparePart) { this.sparePart = sparePart; }
    public BigDecimal getQuantity() { return quantity; }
    public void setQuantity(BigDecimal quantity) { this.quantity = quantity; }
    public BigDecimal getActualCost() { return actualCost; }
    public void setActualCost(BigDecimal actualCost) { this.actualCost = actualCost; }
}
