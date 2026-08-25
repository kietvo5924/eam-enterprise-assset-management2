package com.eam.api.repositories;

import com.eam.api.models.entities.AssetCategory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface AssetCategoryRepository extends JpaRepository<AssetCategory, UUID> {
    Page<AssetCategory> findByTenantId(String tenantId, Pageable pageable);
    List<AssetCategory> findByTenantId(String tenantId);
    Optional<AssetCategory> findByIdAndTenantId(UUID id, String tenantId);
    boolean existsByNameAndTenantId(String name, String tenantId);
}
