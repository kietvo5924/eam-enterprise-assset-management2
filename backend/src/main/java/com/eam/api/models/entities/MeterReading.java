package com.eam.api.models.entities;

import jakarta.persistence.*;
import org.hibernate.annotations.GenericGenerator;
import java.time.ZonedDateTime;
import java.util.UUID;
import java.math.BigDecimal;

@Entity
@Table(name = "meter_readings")
@EntityListeners(com.eam.api.core.audit.AuditTrailListener.class)
public class MeterReading extends BaseTenantEntity {

    @Id
    @GeneratedValue(generator = "UUID")
    @GenericGenerator(name = "UUID", strategy = "org.hibernate.id.UUIDGenerator")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "asset_id", nullable = false)
    private Asset asset;

    @Column(name = "reading_value", nullable = false, precision = 19, scale = 2)
    private BigDecimal readingValue;

    @Column(name = "reading_date", nullable = false)
    private ZonedDateTime readingDate;

    @Column(length = 50)
    private String unit;

    @Column(columnDefinition = "TEXT")
    private String remarks;

    @Column(name = "created_at", updatable = false)
    private ZonedDateTime createdAt;

    @Column(name = "created_by", updatable = false)
    private UUID createdBy;

    @PrePersist
    protected void onCreate() {
        createdAt = ZonedDateTime.now();
        if (readingDate == null) {
            readingDate = ZonedDateTime.now();
        }
    }

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }

    public Asset getAsset() { return asset; }
    public void setAsset(Asset asset) { this.asset = asset; }

    public BigDecimal getReadingValue() { return readingValue; }
    public void setReadingValue(BigDecimal readingValue) { this.readingValue = readingValue; }

    public ZonedDateTime getReadingDate() { return readingDate; }
    public void setReadingDate(ZonedDateTime readingDate) { this.readingDate = readingDate; }

    public String getUnit() { return unit; }
    public void setUnit(String unit) { this.unit = unit; }

    public String getRemarks() { return remarks; }
    public void setRemarks(String remarks) { this.remarks = remarks; }

    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }

    public UUID getCreatedBy() { return createdBy; }
    public void setCreatedBy(UUID createdBy) { this.createdBy = createdBy; }
}
