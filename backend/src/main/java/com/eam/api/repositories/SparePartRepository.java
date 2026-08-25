package com.eam.api.repositories;

import com.eam.api.models.entities.SparePart;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface SparePartRepository extends JpaRepository<SparePart, UUID> {
    Page<SparePart> findByTenantId(String tenantId, Pageable pageable);
    Optional<SparePart> findByIdAndTenantId(UUID id, String tenantId);
}
