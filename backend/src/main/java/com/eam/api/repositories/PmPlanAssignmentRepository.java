package com.eam.api.repositories;

import com.eam.api.models.entities.PmPlanAssignment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.UUID;
import java.util.List;

@Repository
public interface PmPlanAssignmentRepository extends JpaRepository<PmPlanAssignment, UUID> {
    
    List<PmPlanAssignment> findByPmPlanId(UUID pmPlanId);

    List<PmPlanAssignment> findByAssetId(UUID assetId);
    
    boolean existsByPmPlanIdAndAssetId(UUID pmPlanId, UUID assetId);

    @org.springframework.data.jpa.repository.Query("SELECT a FROM PmPlanAssignment a JOIN FETCH a.pmPlan p JOIN FETCH a.asset ast WHERE p.tenantId = :tenantId AND p.isActive = true AND a.status = 'ACTIVE' " +
            "AND (cast(:assetId as uuid) IS NULL OR ast.id = :assetId) " +
            "AND (cast(:categoryId as uuid) IS NULL OR ast.category.id = :categoryId)")
    List<PmPlanAssignment> findActiveAssignmentsByTenantId(
            @org.springframework.data.repository.query.Param("tenantId") String tenantId,
            @org.springframework.data.repository.query.Param("assetId") UUID assetId,
            @org.springframework.data.repository.query.Param("categoryId") UUID categoryId);

    @org.springframework.data.jpa.repository.Query("SELECT a FROM PmPlanAssignment a JOIN FETCH a.pmPlan p JOIN FETCH a.asset ast WHERE p.isActive = true AND a.status = 'ACTIVE'")
    List<PmPlanAssignment> findAllActiveAssignments();
}
