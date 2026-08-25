package com.eam.api.repositories;

import com.eam.api.models.entities.PmPlanMaterial;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface PmPlanMaterialRepository extends JpaRepository<PmPlanMaterial, UUID> {
    List<PmPlanMaterial> findByPmPlanId(UUID pmPlanId);
}
