package com.eam.api.repositories;

import com.eam.api.models.entities.PmPlan;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface PmPlanRepository extends JpaRepository<PmPlan, UUID> {
    long countByTenantId(String tenantId);
}
