package com.eam.api.repositories;

import com.eam.api.models.entities.Location;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface LocationRepository extends JpaRepository<Location, UUID> {
    Page<Location> findByTenantId(String tenantId, Pageable pageable);
    List<Location> findByTenantId(String tenantId);
    Page<Location> findByTenantIdAndIsActiveTrue(String tenantId, Pageable pageable);
    Optional<Location> findByIdAndTenantIdAndIsActiveTrue(UUID id, String tenantId);
    Optional<Location> findByIdAndTenantId(UUID id, String tenantId);
}
