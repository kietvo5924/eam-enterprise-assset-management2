package com.eam.api.models.dtos;

import java.time.ZonedDateTime;
import java.util.UUID;
import java.math.BigDecimal;

public class MeterReadingDto {
    private UUID id;
    private UUID assetId;
    private BigDecimal readingValue;
    private ZonedDateTime readingDate;
    private String unit;
    private String remarks;
    private UUID createdBy;
    private ZonedDateTime createdAt;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }

    public UUID getAssetId() { return assetId; }
    public void setAssetId(UUID assetId) { this.assetId = assetId; }

    public BigDecimal getReadingValue() { return readingValue; }
    public void setReadingValue(BigDecimal readingValue) { this.readingValue = readingValue; }

    public ZonedDateTime getReadingDate() { return readingDate; }
    public void setReadingDate(ZonedDateTime readingDate) { this.readingDate = readingDate; }

    public String getUnit() { return unit; }
    public void setUnit(String unit) { this.unit = unit; }

    public String getRemarks() { return remarks; }
    public void setRemarks(String remarks) { this.remarks = remarks; }

    public UUID getCreatedBy() { return createdBy; }
    public void setCreatedBy(UUID createdBy) { this.createdBy = createdBy; }

    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }
}
