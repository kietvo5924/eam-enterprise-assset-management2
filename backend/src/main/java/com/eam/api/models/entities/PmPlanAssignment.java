package com.eam.api.models.entities;

import jakarta.persistence.*;
import org.hibernate.annotations.GenericGenerator;
import java.time.ZonedDateTime;
import java.util.UUID;
import java.math.BigDecimal;

import com.eam.api.models.enums.PmAssignmentStatus;

@Entity
@Table(name = "pm_plan_assignments", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"tenant_id", "pm_plan_id", "asset_id"})
})
@EntityListeners(com.eam.api.core.audit.AuditTrailListener.class)
public class PmPlanAssignment extends BaseTenantEntity {

    @Id
    @GeneratedValue(generator = "UUID")
    @GenericGenerator(name = "UUID", strategy = "org.hibernate.id.UUIDGenerator")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "pm_plan_id", nullable = false)
    private PmPlan pmPlan;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "asset_id", nullable = false)
    private Asset asset;

    @Column(name = "assigned_at", nullable = false, updatable = false)
    private ZonedDateTime assignedAt;

    @Column(name = "baseline_meter_reading", precision = 19, scale = 2)
    private BigDecimal baselineMeterReading;

    @Column(name = "last_triggered_at")
    private ZonedDateTime lastTriggeredAt;

    @Column(name = "last_triggered_meter", precision = 19, scale = 2)
    private BigDecimal lastTriggeredMeter;

    @Column(name = "created_at", updatable = false)
    private ZonedDateTime createdAt;

    @Column(name = "created_by", updatable = false)
    private UUID createdBy;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 50)
    private PmAssignmentStatus status = PmAssignmentStatus.ACTIVE;

    @PrePersist
    protected void onCreate() {
        ZonedDateTime now = ZonedDateTime.now();
        createdAt = now;
        if (assignedAt == null) {
            assignedAt = now;
        }
    }

    // Getters and Setters

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }

    public PmPlan getPmPlan() { return pmPlan; }
    public void setPmPlan(PmPlan pmPlan) { this.pmPlan = pmPlan; }

    public Asset getAsset() { return asset; }
    public void setAsset(Asset asset) { this.asset = asset; }

    public ZonedDateTime getAssignedAt() { return assignedAt; }
    public void setAssignedAt(ZonedDateTime assignedAt) { this.assignedAt = assignedAt; }

    public BigDecimal getBaselineMeterReading() { return baselineMeterReading; }
    public void setBaselineMeterReading(BigDecimal baselineMeterReading) { this.baselineMeterReading = baselineMeterReading; }

    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }

    public UUID getCreatedBy() { return createdBy; }
    public void setCreatedBy(UUID createdBy) { this.createdBy = createdBy; }

    public PmAssignmentStatus getStatus() { return status; }
    public void setStatus(PmAssignmentStatus status) { this.status = status; }

    public ZonedDateTime getLastTriggeredAt() { return lastTriggeredAt; }
    public void setLastTriggeredAt(ZonedDateTime lastTriggeredAt) { this.lastTriggeredAt = lastTriggeredAt; }

    public BigDecimal getLastTriggeredMeter() { return lastTriggeredMeter; }
    public void setLastTriggeredMeter(BigDecimal lastTriggeredMeter) { this.lastTriggeredMeter = lastTriggeredMeter; }
}
