package com.eam.api.models.entities;

import jakarta.persistence.*;
import org.hibernate.annotations.GenericGenerator;
import java.time.ZonedDateTime;
import java.util.UUID;
import java.math.BigDecimal;
import com.eam.api.models.enums.PmTriggerType;
import com.eam.api.models.enums.PmIntervalUnit;

@Entity
@Table(name = "pm_plans")
@EntityListeners(com.eam.api.core.audit.AuditTrailListener.class)
public class PmPlan extends BaseTenantEntity {

    @Id
    @GeneratedValue(generator = "UUID")
    @GenericGenerator(name = "UUID", strategy = "org.hibernate.id.UUIDGenerator")
    private UUID id;

    @Column(nullable = false)
    private String name;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Enumerated(EnumType.STRING)
    @Column(name = "trigger_type", nullable = false, length = 50)
    private PmTriggerType triggerType;

    @Column(name = "interval_value", precision = 19, scale = 2)
    private BigDecimal intervalValue;

    @Enumerated(EnumType.STRING)
    @Column(name = "interval_unit", length = 50)
    private PmIntervalUnit intervalUnit;

    @Column(name = "is_active", nullable = false)
    private Boolean isActive = true;

    @Column(name = "is_floating_schedule", nullable = false)
    private Boolean isFloatingSchedule = false;

    @Column(name = "suppress_if_pending", nullable = false)
    private Boolean suppressIfPending = true;

    @Column(name = "lead_time_days")
    private Integer leadTimeDays = 0;

    @Column(name = "estimated_duration_minutes")
    private Integer estimatedDurationMinutes;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "assignee_id")
    private User assignee;

    @OneToMany(mappedBy = "pmPlan", fetch = FetchType.LAZY, cascade = CascadeType.ALL, orphanRemoval = true)
    private java.util.List<PmPlanChecklistItem> checklists = new java.util.ArrayList<>();

    @OneToMany(mappedBy = "pmPlan", fetch = FetchType.LAZY, cascade = CascadeType.ALL, orphanRemoval = true)
    private java.util.List<PmPlanMaterial> materials = new java.util.ArrayList<>();

    @Column(name = "created_at", updatable = false)
    private ZonedDateTime createdAt;

    @Column(name = "updated_at")
    private ZonedDateTime updatedAt;

    @Column(name = "created_by", updatable = false)
    private UUID createdBy;

    @Column(name = "updated_by")
    private UUID updatedBy;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "created_by", insertable = false, updatable = false)
    private User creator;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "updated_by", insertable = false, updatable = false)
    private User updater;

    @PrePersist
    protected void onCreate() {
        createdAt = ZonedDateTime.now();
        updatedAt = ZonedDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = ZonedDateTime.now();
    }

    // Getters and Setters

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }

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

    public Boolean getIsActive() { return isActive; }
    public void setIsActive(Boolean isActive) { this.isActive = isActive; }

    public Boolean getIsFloatingSchedule() { return isFloatingSchedule; }
    public void setIsFloatingSchedule(Boolean isFloatingSchedule) { this.isFloatingSchedule = isFloatingSchedule; }

    public Boolean getSuppressIfPending() { return suppressIfPending; }
    public void setSuppressIfPending(Boolean suppressIfPending) { this.suppressIfPending = suppressIfPending; }

    public Integer getLeadTimeDays() { return leadTimeDays; }
    public void setLeadTimeDays(Integer leadTimeDays) { this.leadTimeDays = leadTimeDays; }

    public Integer getEstimatedDurationMinutes() { return estimatedDurationMinutes; }
    public void setEstimatedDurationMinutes(Integer estimatedDurationMinutes) { this.estimatedDurationMinutes = estimatedDurationMinutes; }

    public User getAssignee() { return assignee; }
    public void setAssignee(User assignee) { this.assignee = assignee; }

    public java.util.List<PmPlanChecklistItem> getChecklists() { return checklists; }
    public void setChecklists(java.util.List<PmPlanChecklistItem> checklists) { this.checklists = checklists; }

    public java.util.List<PmPlanMaterial> getMaterials() { return materials; }
    public void setMaterials(java.util.List<PmPlanMaterial> materials) { this.materials = materials; }

    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }

    public ZonedDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(ZonedDateTime updatedAt) { this.updatedAt = updatedAt; }

    public UUID getCreatedBy() { return createdBy; }
    public void setCreatedBy(UUID createdBy) { this.createdBy = createdBy; }

    public UUID getUpdatedBy() { return updatedBy; }
    public void setUpdatedBy(UUID updatedBy) { this.updatedBy = updatedBy; }

    public User getCreator() { return creator; }
    public void setCreator(User creator) { this.creator = creator; }

    public User getUpdater() { return updater; }
    public void setUpdater(User updater) { this.updater = updater; }
}
