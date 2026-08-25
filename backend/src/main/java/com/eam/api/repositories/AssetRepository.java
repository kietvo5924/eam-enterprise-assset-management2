package com.eam.api.repositories;

import com.eam.api.models.entities.Asset;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface AssetRepository extends JpaRepository<Asset, UUID>, JpaSpecificationExecutor<Asset> {
    Page<Asset> findByTenantIdAndIsActiveTrue(String tenantId, Pageable pageable);
    Optional<Asset> findByIdAndTenantIdAndIsActiveTrue(UUID id, String tenantId);
    Optional<Asset> findByQrCodeAndTenantIdAndIsActiveTrue(String qrCode, String tenantId);
    boolean existsByQrCodeAndTenantId(String qrCode, String tenantId);
}
