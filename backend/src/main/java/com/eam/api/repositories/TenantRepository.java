package com.eam.api.repositories;

import com.eam.api.models.entities.Tenant;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface TenantRepository extends JpaRepository<Tenant, UUID> {
    boolean existsByTenantCode(String tenantCode);
}
