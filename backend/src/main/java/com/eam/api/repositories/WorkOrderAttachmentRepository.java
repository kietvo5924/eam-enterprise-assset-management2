package com.eam.api.repositories;

import com.eam.api.models.entities.WorkOrderAttachment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface WorkOrderAttachmentRepository extends JpaRepository<WorkOrderAttachment, UUID> {
    List<WorkOrderAttachment> findByWorkOrderIdOrderByCreatedAtAsc(UUID workOrderId);
}
