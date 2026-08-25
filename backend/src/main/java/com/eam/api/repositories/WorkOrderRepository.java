package com.eam.api.repositories;

import com.eam.api.models.entities.WorkOrder;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface WorkOrderRepository extends JpaRepository<WorkOrder, UUID> {
    @org.springframework.data.jpa.repository.EntityGraph(attributePaths = {"assignee", "asset", "parentWorkOrder", "creator"})
    Page<WorkOrder> findByTenantId(String tenantId, Pageable pageable);
    Optional<WorkOrder> findByIdAndTenantId(UUID id, String tenantId);
    boolean existsBySourceReferenceAndStatusNotIn(String sourceReference, java.util.Collection<com.eam.api.models.enums.WorkOrderStatus> statuses);
    boolean existsBySourceReference(String sourceReference);
    boolean existsBySourceReferenceStartingWith(String sourceReferencePrefix);
    
    Optional<WorkOrder> findFirstBySourceReferenceAndStatusOrderByCompletedAtDesc(String sourceReference, com.eam.api.models.enums.WorkOrderStatus status);

    long countByTenantId(String tenantId);
    long countByTenantIdAndStatus(String tenantId, com.eam.api.models.enums.WorkOrderStatus status);
    
    @org.springframework.data.jpa.repository.Query("SELECT COUNT(w) FROM WorkOrder w WHERE w.tenantId = :tenantId AND w.status NOT IN :statuses AND w.deadline < CURRENT_TIMESTAMP")
    long countOverdueByTenantId(
        @org.springframework.data.repository.query.Param("tenantId") String tenantId,
        @org.springframework.data.repository.query.Param("statuses") java.util.Collection<com.eam.api.models.enums.WorkOrderStatus> statuses
    );

    @org.springframework.data.jpa.repository.Query("SELECT COUNT(w) FROM WorkOrder w WHERE w.tenantId = :tenantId AND w.sourceReference LIKE 'PM-%'")
    long countPmWorkOrdersByTenantId(@org.springframework.data.repository.query.Param("tenantId") String tenantId);

    @org.springframework.data.jpa.repository.Query("SELECT COUNT(w) FROM WorkOrder w WHERE w.tenantId = :tenantId AND w.status = 'COMPLETED' AND w.sourceReference LIKE 'PM-%'")
    long countCompletedPmWorkOrdersByTenantId(@org.springframework.data.repository.query.Param("tenantId") String tenantId);

    @org.springframework.data.jpa.repository.Query("SELECT COUNT(w) FROM WorkOrder w WHERE w.tenantId = :tenantId AND w.status NOT IN :statuses AND w.deadline < CURRENT_TIMESTAMP AND w.sourceReference LIKE 'PM-%'")
    long countMissedPmWorkOrdersByTenantId(
        @org.springframework.data.repository.query.Param("tenantId") String tenantId,
        @org.springframework.data.repository.query.Param("statuses") java.util.Collection<com.eam.api.models.enums.WorkOrderStatus> statuses
    );

    @org.springframework.data.jpa.repository.EntityGraph(attributePaths = {"asset"})
    @org.springframework.data.jpa.repository.Query("SELECT w FROM WorkOrder w WHERE w.tenantId = :tenantId " +
            "AND (w.deadline BETWEEN :startDate AND :endDate OR (w.deadline IS NULL AND w.createdAt BETWEEN :startDate AND :endDate)) " +
            "AND (cast(:assetId as uuid) IS NULL OR w.asset.id = :assetId) " +
            "AND (cast(:categoryId as uuid) IS NULL OR w.asset.category.id = :categoryId) " +
            "AND (:status IS NULL OR w.status = :status)")
    java.util.List<WorkOrder> findCalendarEventsByTenantId(
            @org.springframework.data.repository.query.Param("tenantId") String tenantId, 
            @org.springframework.data.repository.query.Param("startDate") java.time.ZonedDateTime startDate, 
            @org.springframework.data.repository.query.Param("endDate") java.time.ZonedDateTime endDate,
            @org.springframework.data.repository.query.Param("assetId") UUID assetId,
            @org.springframework.data.repository.query.Param("categoryId") UUID categoryId,
            @org.springframework.data.repository.query.Param("status") com.eam.api.models.enums.WorkOrderStatus status);
}
