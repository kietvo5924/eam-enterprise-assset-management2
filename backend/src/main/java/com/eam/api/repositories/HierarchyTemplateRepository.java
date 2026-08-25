package com.eam.api.repositories;

import com.eam.api.models.entities.HierarchyTemplate;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;

@Repository
public interface HierarchyTemplateRepository extends JpaRepository<HierarchyTemplate, UUID> {
    Page<HierarchyTemplate> findByTenantIdOrderByPathAsc(String tenantId, Pageable pageable);
    List<HierarchyTemplate> findByTenantId(String tenantId);
    Optional<HierarchyTemplate> findByIdAndTenantId(UUID id, String tenantId);
    boolean existsByNameAndTenantId(String name, String tenantId);
    
    @Query(value = "SELECT * FROM hierarchy_templates WHERE tenant_id = CAST(:tenantId AS uuid) AND path <@ CAST(:path AS ltree)", nativeQuery = true)
    List<HierarchyTemplate> findDescendants(@Param("tenantId") String tenantId, @Param("path") String path);
}
