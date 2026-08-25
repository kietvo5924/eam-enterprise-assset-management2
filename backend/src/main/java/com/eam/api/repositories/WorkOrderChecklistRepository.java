package com.eam.api.repositories;

import com.eam.api.models.entities.WorkOrderChecklistItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface WorkOrderChecklistRepository extends JpaRepository<WorkOrderChecklistItem, UUID> {
    List<WorkOrderChecklistItem> findByWorkOrderIdOrderByCreatedAtAsc(UUID workOrderId);
}
