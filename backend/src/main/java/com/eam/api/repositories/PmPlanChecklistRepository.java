package com.eam.api.repositories;

import com.eam.api.models.entities.PmPlanChecklistItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface PmPlanChecklistRepository extends JpaRepository<PmPlanChecklistItem, UUID> {
    List<PmPlanChecklistItem> findByPmPlanId(UUID pmPlanId);
}
