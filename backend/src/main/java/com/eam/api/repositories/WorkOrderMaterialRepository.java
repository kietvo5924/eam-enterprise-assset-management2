package com.eam.api.repositories;

import com.eam.api.models.entities.WorkOrderMaterial;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface WorkOrderMaterialRepository extends JpaRepository<WorkOrderMaterial, UUID> {
    List<WorkOrderMaterial> findByWorkOrderId(UUID workOrderId);
}
