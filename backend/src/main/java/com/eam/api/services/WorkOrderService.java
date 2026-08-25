package com.eam.api.services;

import com.eam.api.core.security.CustomUserDetails;
import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.AssetResponse;
import com.eam.api.models.dtos.WorkOrderCreateRequest;
import com.eam.api.models.dtos.WorkOrderAssignRequest;
import com.eam.api.models.dtos.WorkOrderDto;
import com.eam.api.models.dtos.UserDto;
import com.eam.api.models.dtos.WorkOrderStatusUpdateRequest;
import com.eam.api.models.dtos.WorkOrderChecklistItemRequest;
import com.eam.api.models.dtos.WorkOrderChecklistDto;
import com.eam.api.models.dtos.WorkOrderAttachmentDto;
import com.eam.api.models.enums.WorkOrderStatus;
import com.eam.api.models.entities.Asset;
import com.eam.api.models.entities.WorkOrder;
import com.eam.api.models.entities.User;
import com.eam.api.repositories.AssetRepository;
import com.eam.api.repositories.UserRepository;
import com.eam.api.repositories.WorkOrderRepository;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.eam.api.repositories.PmPlanAssignmentRepository;
import com.eam.api.models.dtos.MaintenanceCalendarEventDto;
import com.eam.api.models.entities.PmPlanAssignment;
import com.eam.api.models.enums.PmTriggerType;
import com.eam.api.models.enums.PmIntervalUnit;

@Service
public class WorkOrderService {

    @org.springframework.beans.factory.annotation.Autowired
    @org.springframework.context.annotation.Lazy
    private com.eam.api.services.PmPlanService pmPlanService;

    private final WorkOrderRepository workOrderRepository;
    private final AssetRepository assetRepository;
    private final UserRepository userRepository;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ObjectMapper objectMapper;
    private final FileStorageService fileStorageService;
    private final AuditLogService auditLogService;
    private final PmPlanAssignmentRepository pmPlanAssignmentRepository;

    public WorkOrderService(WorkOrderRepository workOrderRepository, AssetRepository assetRepository,
            UserRepository userRepository, KafkaTemplate<String, Object> kafkaTemplate, ObjectMapper objectMapper,
            FileStorageService fileStorageService, AuditLogService auditLogService,
            PmPlanAssignmentRepository pmPlanAssignmentRepository) {
        this.workOrderRepository = workOrderRepository;
        this.assetRepository = assetRepository;
        this.userRepository = userRepository;
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
        this.fileStorageService = fileStorageService;
        this.auditLogService = auditLogService;
        this.pmPlanAssignmentRepository = pmPlanAssignmentRepository;
    }

    @Transactional(readOnly = true)
    public Page<WorkOrderDto> getWorkOrders(Pageable pageable) {
        String tenantId = TenantContext.getCurrentTenant();
        return workOrderRepository.findByTenantId(tenantId, pageable)
                .map(this::mapToDto);
    }

    @Transactional(readOnly = true)
    public com.eam.api.models.dtos.WorkOrderKpiDto getWorkOrderKpis() {
        String tenantId = TenantContext.getCurrentTenant();

        long total = workOrderRepository.countByTenantId(tenantId);
        long inProgress = workOrderRepository.countByTenantIdAndStatus(tenantId, WorkOrderStatus.IN_PROGRESS);
        long completed = workOrderRepository.countByTenantIdAndStatus(tenantId, WorkOrderStatus.COMPLETED);

        java.util.List<WorkOrderStatus> inactiveStatuses = java.util.Arrays.asList(
                WorkOrderStatus.COMPLETED,
                WorkOrderStatus.CANCELED);
        long overdue = workOrderRepository.countOverdueByTenantId(tenantId, inactiveStatuses);

        com.eam.api.models.dtos.WorkOrderKpiDto dto = new com.eam.api.models.dtos.WorkOrderKpiDto();
        dto.setTotalWorkOrders(total);
        dto.setInProgressWorkOrders(inProgress);
        dto.setCompletedWorkOrders(completed);
        dto.setOverdueWorkOrders(overdue);
        return dto;
    }

    @Transactional(readOnly = true)
    public WorkOrderDto getWorkOrderById(UUID id) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found with id: " + id));
        return mapToDto(workOrder);
    }

    @Transactional(readOnly = true)
    public List<MaintenanceCalendarEventDto> getCalendarEvents(ZonedDateTime startDate, ZonedDateTime endDate,
            UUID assetId, UUID categoryId, String status) {
        String tenantId = TenantContext.getCurrentTenant();
        List<MaintenanceCalendarEventDto> events = new ArrayList<>();

        WorkOrderStatus parsedStatus = null;
        if (status != null && !status.isEmpty() && !status.equals("SCHEDULED")) {
            parsedStatus = WorkOrderStatus.valueOf(status);
        }

        // 1. Fetch Work Orders
        List<WorkOrder> workOrders = workOrderRepository.findCalendarEventsByTenantId(tenantId, startDate, endDate,
                assetId, categoryId, parsedStatus);
        for (WorkOrder wo : workOrders) {
            MaintenanceCalendarEventDto event = new MaintenanceCalendarEventDto();
            event.setId(wo.getId().toString());
            event.setTitle(wo.getTitle());
            event.setEventDate(wo.getDeadline() != null ? wo.getDeadline() : wo.getCreatedAt());
            event.setEventType("WORK_ORDER");
            event.setStatus(wo.getStatus().name());
            event.setPriority(wo.getPriority());
            if (wo.getAsset() != null) {
                event.setAssetId(wo.getAsset().getId());
                event.setAssetName(wo.getAsset().getName());
            }
            event.setOriginalData(mapToDto(wo));
            events.add(event);
        }

        // If status filter is applied and it's not SCHEDULED, do not project PM Plans
        // (which are SCHEDULED)
        if (status != null && !status.equals("SCHEDULED") && !status.isEmpty()) {
            return events;
        }

        // 2. Fetch active PM Plan Assignments and project their next triggers
        List<PmPlanAssignment> assignments = pmPlanAssignmentRepository.findActiveAssignmentsByTenantId(tenantId,
                assetId, categoryId);

        for (PmPlanAssignment assignment : assignments) {
            if (assignment.getPmPlan().getTriggerType() == PmTriggerType.TIME) {
                ZonedDateTime referenceDate = assignment.getLastTriggeredAt() != null
                        ? assignment.getLastTriggeredAt()
                        : assignment.getCreatedAt();

                ZonedDateTime dueDate = referenceDate;
                if (assignment.getPmPlan().getIntervalUnit() != null
                        && assignment.getPmPlan().getIntervalValue() != null) {
                    long interval = assignment.getPmPlan().getIntervalValue().longValue();
                    if (interval <= 0)
                        continue;

                    PmIntervalUnit unit = assignment.getPmPlan().getIntervalUnit();
                    // We can project future occurrences up to endDate
                    while (!dueDate.isAfter(endDate)) {
                        switch (unit) {
                            case DAYS:
                                dueDate = dueDate.plusDays(interval);
                                break;
                            case WEEKS:
                                dueDate = dueDate.plusWeeks(interval);
                                break;
                            case MONTHS:
                                dueDate = dueDate.plusMonths(interval);
                                break;
                            case YEARS:
                                dueDate = dueDate.plusYears(interval);
                                break;
                            default:
                                break;
                        }

                        if (unit == null)
                            break;

                        // Check if the NEW projected dueDate is within range
                        if (!dueDate.isBefore(startDate) && !dueDate.isAfter(endDate)) {
                            MaintenanceCalendarEventDto event = new MaintenanceCalendarEventDto();
                            event.setId(assignment.getId().toString() + "_proj_" + dueDate.toInstant().toEpochMilli());
                            event.setTitle("PM: " + assignment.getPmPlan().getName());
                            event.setEventDate(dueDate);
                            event.setEventType("PM_PLAN");
                            event.setStatus("SCHEDULED");
                            event.setPriority("MEDIUM");
                            if (assignment.getAsset() != null) {
                                event.setAssetId(assignment.getAsset().getId());
                                event.setAssetName(assignment.getAsset().getName());
                            }

                            if (assignment.getPmPlan() != null && pmPlanService != null) {
                                event.setOriginalData(pmPlanService.mapToDto(assignment.getPmPlan()));
                            }
                            events.add(event);
                        }
                    }
                }
            }
        }

        return events;
    }

    @Transactional
    public void generateFromPmPlan(com.eam.api.models.events.MaintenanceTriggeredEvent event) {
        String sourceReference = "PM_" + event.getPmPlanId() + "_ASSET_" + event.getAssetId();

        java.util.Optional<Asset> assetOpt = assetRepository.findById(event.getAssetId());
        if (assetOpt.isEmpty()) {
            return;
        }

        // Fetch PmPlan
        java.util.Optional<com.eam.api.models.entities.PmPlan> pmPlanOpt = context
                .getBean(com.eam.api.repositories.PmPlanRepository.class).findById(event.getPmPlanId());
        if (pmPlanOpt.isEmpty()) {
            return;
        }
        com.eam.api.models.entities.PmPlan pmPlan = pmPlanOpt.get();

        WorkOrder wo = new WorkOrder();
        wo.setTenantId(event.getTenantId());
        wo.setAsset(assetOpt.get());
        wo.setTitle(event.getTitle());
        wo.setDescription(event.getDescription());
        wo.setPriority(event.getPriority());
        wo.setStatus(WorkOrderStatus.CREATED);
        wo.setSourceReference(sourceReference);
        wo.setDeadline(event.getDueDate());
        wo.setEstimatedDurationMinutes(pmPlan.getEstimatedDurationMinutes());

        if (pmPlan.getAssignee() != null) {
            wo.setAssignedTo(pmPlan.getAssignee().getId());
        }
        wo.setCreatedBy(pmPlan.getCreatedBy());
        wo.setUpdatedBy(pmPlan.getUpdatedBy());

        WorkOrder savedWorkOrder = workOrderRepository.save(wo);

        // Clone Checklists
        if (pmPlan.getChecklists() != null && !pmPlan.getChecklists().isEmpty()) {
            com.eam.api.repositories.WorkOrderChecklistRepository checklistRepo = getChecklistRepository();
            for (com.eam.api.models.entities.PmPlanChecklistItem pc : pmPlan.getChecklists()) {
                com.eam.api.models.entities.WorkOrderChecklistItem wc = new com.eam.api.models.entities.WorkOrderChecklistItem();
                wc.setTenantId(event.getTenantId());
                wc.setWorkOrder(savedWorkOrder);
                wc.setItemName(pc.getItemName());
                wc.setInputType(pc.getInputType());
                wc.setExpectedValue(pc.getExpectedValue());
                wc.setIsMandatory(pc.getIsMandatory());
                wc.setCompleted(false);
                wc.setCreatedBy(pmPlan.getCreatedBy());
                wc.setUpdatedBy(pmPlan.getUpdatedBy());
                checklistRepo.save(wc);
            }
        }

        // Clone Materials
        if (pmPlan.getMaterials() != null && !pmPlan.getMaterials().isEmpty()) {
            com.eam.api.repositories.WorkOrderMaterialRepository materialRepo = context
                    .getBean(com.eam.api.repositories.WorkOrderMaterialRepository.class);
            com.eam.api.repositories.SparePartRepository sparePartRepo = context
                    .getBean(com.eam.api.repositories.SparePartRepository.class);
            for (com.eam.api.models.entities.PmPlanMaterial pm : pmPlan.getMaterials()) {
                com.eam.api.models.entities.SparePart part = pm.getSparePart();
                if (part != null && part.getQuantityInStock() != null) {
                    part.setQuantityInStock(part.getQuantityInStock().subtract(pm.getQuantity()));
                    sparePartRepo.save(part);
                }

                com.eam.api.models.entities.WorkOrderMaterial wm = new com.eam.api.models.entities.WorkOrderMaterial();
                wm.setTenantId(event.getTenantId());
                wm.setWorkOrder(savedWorkOrder);
                wm.setSparePart(pm.getSparePart());
                wm.setQuantity(pm.getQuantity());
                wm.setCreatedBy(pmPlan.getCreatedBy());
                wm.setUpdatedBy(pmPlan.getUpdatedBy());
                materialRepo.save(wm);
            }
        }

        com.eam.api.models.events.WorkOrderCreatedEvent woCreatedEvent = new com.eam.api.models.events.WorkOrderCreatedEvent(
                event.getTenantId(),
                savedWorkOrder.getId(),
                event.getAssetId(),
                event.getTitle(),
                event.getPriority());

        kafkaTemplate.send("workorder.events", woCreatedEvent);
    }

    @Transactional
    public WorkOrderDto createWorkOrder(WorkOrderCreateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();

        WorkOrder workOrder = new WorkOrder();
        workOrder.setTenantId(tenantId);

        if (request.getParentWorkOrderId() != null) {
            WorkOrder parent = workOrderRepository.findByIdAndTenantId(request.getParentWorkOrderId(), tenantId)
                    .orElseThrow(() -> new IllegalArgumentException("Parent Work Order not found"));
            if (parent.getStatus() != WorkOrderStatus.COMPLETED) {
                throw new IllegalArgumentException(
                        "Parent Work Order must be in COMPLETED status to create a follow-up");
            }
            workOrder.setParentId(parent.getId());
            workOrder.setParentWorkOrder(parent);
            workOrder.setAsset(parent.getAsset());
        } else {
            Asset asset = assetRepository.findByIdAndTenantIdAndIsActiveTrue(request.getAssetId(), tenantId)
                    .orElseThrow(() -> new IllegalArgumentException("Asset not found or inactive"));
            workOrder.setAsset(asset);
        }

        workOrder.setTitle(request.getTitle());
        workOrder.setDescription(request.getDescription());
        workOrder.setPriority(request.getPriority());
        workOrder.setStatus(WorkOrderStatus.CREATED);
        workOrder.setDeadline(request.getDeadline());
        workOrder.setEstimatedDurationMinutes(request.getEstimatedDurationMinutes());

        UUID currentUserId = getCurrentUserId();
        workOrder.setCreatedBy(currentUserId);
        workOrder.setUpdatedBy(currentUserId);

        WorkOrder savedWorkOrder = workOrderRepository.save(workOrder);

        // Save Checklists
        if (request.getChecklists() != null && !request.getChecklists().isEmpty()) {
            com.eam.api.repositories.WorkOrderChecklistRepository checklistRepo = getChecklistRepository();
            for (com.eam.api.models.dtos.PmPlanChecklistDto pc : request.getChecklists()) {
                com.eam.api.models.entities.WorkOrderChecklistItem wc = new com.eam.api.models.entities.WorkOrderChecklistItem();
                wc.setTenantId(tenantId);
                wc.setWorkOrder(savedWorkOrder);
                wc.setItemName(pc.getItemName());
                wc.setInputType(pc.getInputType());
                wc.setExpectedValue(pc.getExpectedValue());
                wc.setIsMandatory(pc.getIsMandatory() != null ? pc.getIsMandatory() : false);
                wc.setCompleted(false);
                wc.setCreatedBy(currentUserId);
                wc.setUpdatedBy(currentUserId);
                checklistRepo.save(wc);
            }
        }

        // Save Materials
        if (request.getMaterials() != null && !request.getMaterials().isEmpty()) {
            com.eam.api.repositories.WorkOrderMaterialRepository materialRepo = context
                    .getBean(com.eam.api.repositories.WorkOrderMaterialRepository.class);
            com.eam.api.repositories.SparePartRepository sparePartRepo = context
                    .getBean(com.eam.api.repositories.SparePartRepository.class);
            for (com.eam.api.models.dtos.PmPlanMaterialDto pm : request.getMaterials()) {
                com.eam.api.models.entities.SparePart part = sparePartRepo
                        .findByIdAndTenantId(pm.getSparePartId(), tenantId)
                        .orElseThrow(() -> new IllegalArgumentException("Spare Part not found"));

                if (part.getQuantityInStock() != null && part.getQuantityInStock().compareTo(pm.getQuantity()) < 0) {
                    throw new IllegalArgumentException("Không đủ số lượng trong kho cho vật tư: " + part.getName());
                }
                if (part.getQuantityInStock() != null) {
                    part.setQuantityInStock(part.getQuantityInStock().subtract(pm.getQuantity()));
                    sparePartRepo.save(part);
                }

                com.eam.api.models.entities.WorkOrderMaterial wm = new com.eam.api.models.entities.WorkOrderMaterial();
                wm.setTenantId(tenantId);
                wm.setWorkOrder(savedWorkOrder);
                wm.setSparePart(part);
                wm.setQuantity(pm.getQuantity());
                wm.setCreatedBy(currentUserId);
                wm.setUpdatedBy(currentUserId);
                materialRepo.save(wm);
            }
        }

        auditLogService.logAction(
                com.eam.api.models.enums.ActionType.CREATE,
                "WorkOrder",
                savedWorkOrder.getId().toString());

        return mapToDto(savedWorkOrder);
    }

    @Transactional
    public WorkOrderDto updateWorkOrder(UUID id, WorkOrderCreateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        if (!WorkOrderStatus.CREATED.equals(workOrder.getStatus())
                && !WorkOrderStatus.ASSIGNED.equals(workOrder.getStatus())) {
            throw new IllegalArgumentException("Cannot edit a Work Order that is in progress, completed or canceled");
        }

        if (!workOrder.getAsset().getId().equals(request.getAssetId())) {
            Asset asset = assetRepository.findByIdAndTenantIdAndIsActiveTrue(request.getAssetId(), tenantId)
                    .orElseThrow(() -> new IllegalArgumentException("Asset not found or inactive"));
            workOrder.setAsset(asset);
        }

        workOrder.setTitle(request.getTitle());
        workOrder.setDescription(request.getDescription());
        workOrder.setPriority(request.getPriority());
        workOrder.setDeadline(request.getDeadline());
        workOrder.setEstimatedDurationMinutes(request.getEstimatedDurationMinutes());

        UUID currentUserId = getCurrentUserId();
        workOrder.setUpdatedBy(currentUserId);

        WorkOrder savedWorkOrder = workOrderRepository.save(workOrder);

        // Update Checklists
        if (request.getChecklists() != null) {
            com.eam.api.repositories.WorkOrderChecklistRepository checklistRepo = getChecklistRepository();
            // Delete old ones
            java.util.List<com.eam.api.models.entities.WorkOrderChecklistItem> oldItems = checklistRepo
                    .findByWorkOrderIdOrderByCreatedAtAsc(savedWorkOrder.getId());
            checklistRepo.deleteAll(oldItems);

            for (com.eam.api.models.dtos.PmPlanChecklistDto pc : request.getChecklists()) {
                com.eam.api.models.entities.WorkOrderChecklistItem wc = new com.eam.api.models.entities.WorkOrderChecklistItem();
                wc.setTenantId(tenantId);
                wc.setWorkOrder(savedWorkOrder);
                wc.setItemName(pc.getItemName());
                wc.setInputType(pc.getInputType());
                wc.setExpectedValue(pc.getExpectedValue());
                wc.setIsMandatory(pc.getIsMandatory() != null ? pc.getIsMandatory() : false);
                wc.setCompleted(false);
                wc.setCreatedBy(currentUserId);
                wc.setUpdatedBy(currentUserId);
                checklistRepo.save(wc);
            }
        }

        // Update Materials
        if (request.getMaterials() != null) {
            com.eam.api.repositories.WorkOrderMaterialRepository materialRepo = context
                    .getBean(com.eam.api.repositories.WorkOrderMaterialRepository.class);
            com.eam.api.repositories.SparePartRepository sparePartRepo = context
                    .getBean(com.eam.api.repositories.SparePartRepository.class);

            // Delete old ones and restore inventory
            java.util.List<com.eam.api.models.entities.WorkOrderMaterial> oldMaterials = materialRepo
                    .findByWorkOrderId(savedWorkOrder.getId());
            for (com.eam.api.models.entities.WorkOrderMaterial oldWm : oldMaterials) {
                com.eam.api.models.entities.SparePart part = oldWm.getSparePart();
                if (part != null && part.getQuantityInStock() != null) {
                    part.setQuantityInStock(part.getQuantityInStock().add(oldWm.getQuantity()));
                    sparePartRepo.save(part);
                }
            }
            materialRepo.deleteAll(oldMaterials);

            for (com.eam.api.models.dtos.PmPlanMaterialDto pm : request.getMaterials()) {
                com.eam.api.models.entities.SparePart part = sparePartRepo
                        .findByIdAndTenantId(pm.getSparePartId(), tenantId)
                        .orElseThrow(() -> new IllegalArgumentException("Spare Part not found"));

                if (part.getQuantityInStock() != null && part.getQuantityInStock().compareTo(pm.getQuantity()) < 0) {
                    throw new IllegalArgumentException("Không đủ số lượng trong kho cho vật tư: " + part.getName());
                }
                if (part.getQuantityInStock() != null) {
                    part.setQuantityInStock(part.getQuantityInStock().subtract(pm.getQuantity()));
                    sparePartRepo.save(part);
                }

                com.eam.api.models.entities.WorkOrderMaterial wm = new com.eam.api.models.entities.WorkOrderMaterial();
                wm.setTenantId(tenantId);
                wm.setWorkOrder(savedWorkOrder);
                wm.setSparePart(part);
                wm.setQuantity(pm.getQuantity());
                wm.setCreatedBy(currentUserId);
                wm.setUpdatedBy(currentUserId);
                materialRepo.save(wm);
            }
        }

        return mapToDto(savedWorkOrder);
    }

    @Transactional
    public void deleteWorkOrder(UUID id) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        if (!WorkOrderStatus.CREATED.equals(workOrder.getStatus())
                && !WorkOrderStatus.ASSIGNED.equals(workOrder.getStatus())) {
            throw new IllegalArgumentException(
                    "Only CREATED or ASSIGNED Work Orders can be deleted");
        }

        // Restore inventory for materials
        com.eam.api.repositories.WorkOrderMaterialRepository materialRepo = context
                .getBean(com.eam.api.repositories.WorkOrderMaterialRepository.class);
        com.eam.api.repositories.SparePartRepository sparePartRepo = context
                .getBean(com.eam.api.repositories.SparePartRepository.class);
        java.util.List<com.eam.api.models.entities.WorkOrderMaterial> materials = materialRepo
                .findByWorkOrderId(workOrder.getId());
        for (com.eam.api.models.entities.WorkOrderMaterial wm : materials) {
            com.eam.api.models.entities.SparePart part = wm.getSparePart();
            if (part != null && part.getQuantityInStock() != null) {
                part.setQuantityInStock(part.getQuantityInStock().add(wm.getQuantity()));
                sparePartRepo.save(part);
            }
        }

        if (workOrder.getFollowUpWorkOrders() != null && !workOrder.getFollowUpWorkOrders().isEmpty()) {
            throw new IllegalArgumentException(
                    "Cannot delete a Work Order that has follow-ups. Delete the follow-ups first.");
        }

        java.util.List<com.eam.api.models.entities.WorkOrderChecklistItem> items = getChecklistRepository()
                .findByWorkOrderIdOrderByCreatedAtAsc(workOrder.getId());
        getChecklistRepository().deleteAll(items);

        java.util.List<com.eam.api.models.entities.WorkOrderAttachment> attachments = getAttachmentRepository()
                .findByWorkOrderIdOrderByCreatedAtAsc(workOrder.getId());
        getAttachmentRepository().deleteAll(attachments);

        workOrderRepository.delete(workOrder);

        auditLogService.logAction(
                com.eam.api.models.enums.ActionType.DELETE,
                "WorkOrder",
                id.toString());
    }

    @Transactional
    public WorkOrderDto assignWorkOrder(UUID id, WorkOrderAssignRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        if (WorkOrderStatus.COMPLETED.equals(workOrder.getStatus())
                || WorkOrderStatus.CANCELED.equals(workOrder.getStatus())) {
            throw new IllegalArgumentException("Cannot reassign a completed or canceled work order");
        }

        User assignee = userRepository.findById(request.getAssigneeId())
                .orElseThrow(() -> new IllegalArgumentException("Assignee not found"));

        if (!assignee.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("Assignee not found in this tenant");
        }

        boolean hasPermission = assignee.getRoles().stream()
                .flatMap(r -> r.getPermissions().stream())
                .anyMatch(p -> "work_order:execute".equals(p.getId()));
        if (!hasPermission) {
            throw new IllegalArgumentException("Assignee must have the work_order:execute permission");
        }

        UUID oldAssigneeId = workOrder.getAssignedTo();
        if (oldAssigneeId != null && oldAssigneeId.equals(request.getAssigneeId())) {
            return mapToDto(workOrder);
        }

        boolean isReassigned = oldAssigneeId != null;

        workOrder.setAssignedTo(assignee.getId());
        workOrder.setAssignee(assignee);
        workOrder.setAssignedAt(ZonedDateTime.now());

        if (isReassigned && WorkOrderStatus.IN_PROGRESS.equals(workOrder.getStatus())) {
            workOrder.setStatus(WorkOrderStatus.ASSIGNED);
            workOrder.setActualStartTime(null);
        } else if (WorkOrderStatus.CREATED.equals(workOrder.getStatus())) {
            workOrder.setStatus(WorkOrderStatus.ASSIGNED);
        }

        UUID currentUserId = getCurrentUserId();
        workOrder.setUpdatedBy(currentUserId);

        WorkOrder savedWorkOrder = workOrderRepository.save(workOrder);

        // Emit Kafka event
        String eventType = isReassigned ? "work_order.reassigned" : "work_order.assigned";
        Map<String, Object> payload = new HashMap<>();
        payload.put("workOrderId", savedWorkOrder.getId());
        payload.put("newAssigneeId", assignee.getId());
        payload.put("oldAssigneeId", oldAssigneeId);
        payload.put("tenantId", tenantId);

        try {
            String jsonPayload = objectMapper.writeValueAsString(payload);
            kafkaTemplate.send("work_orders_topic", eventType, jsonPayload);
        } catch (Exception e) {
            throw new RuntimeException("Failed to serialize Kafka event payload", e);
        }

        auditLogService.logAction(
                com.eam.api.models.enums.ActionType.UPDATE,
                "WorkOrder",
                savedWorkOrder.getId().toString());

        return mapToDto(savedWorkOrder);
    }

    @Transactional
    public WorkOrderDto updateWorkOrderStatus(UUID id, WorkOrderStatusUpdateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        UUID currentUserId = getCurrentUserId();
        WorkOrderStatus currentStatus = workOrder.getStatus();
        WorkOrderStatus newStatus = request.getStatus();

        if (currentStatus.equals(newStatus)) {
            return mapToDto(workOrder);
        }

        // Validate state machine flow
        if (newStatus == WorkOrderStatus.ASSIGNED) {
            throw new IllegalArgumentException("Cannot manually change status to ASSIGNED");
        }

        if (newStatus == WorkOrderStatus.IN_PROGRESS) {
            if (currentStatus != WorkOrderStatus.ASSIGNED) {
                throw new IllegalArgumentException("Work Order can only be started from ASSIGNED state");
            }
            if (!currentUserId.equals(workOrder.getAssignedTo())) {
                throw new IllegalArgumentException("Only the assignee can start the Work Order");
            }
            workOrder.setActualStartTime(ZonedDateTime.now());
        }

        if (newStatus == WorkOrderStatus.COMPLETED) {
            if (currentStatus != WorkOrderStatus.IN_PROGRESS) {
                throw new IllegalArgumentException("Work Order can only be completed from IN_PROGRESS state");
            }
            if (!currentUserId.equals(workOrder.getAssignedTo())) {
                throw new IllegalArgumentException("Only the assignee can complete the Work Order");
            }

            boolean hasNotes = workOrder.getResolutionNotes() != null
                    && !workOrder.getResolutionNotes().trim().isEmpty();
            boolean hasAttachments = !getAttachmentRepository().findByWorkOrderIdOrderByCreatedAtAsc(id).isEmpty();
            if (!hasNotes && !hasAttachments) {
                throw new IllegalArgumentException(
                        "Vui lòng nhập ghi chú sửa chữa hoặc tải lên ít nhất một hình ảnh minh chứng trước khi hoàn thành công việc.");
            }

            // Verify Mandatory Checklists
            java.util.List<com.eam.api.models.entities.WorkOrderChecklistItem> items = getChecklistRepository()
                    .findByWorkOrderIdOrderByCreatedAtAsc(id);
            for (com.eam.api.models.entities.WorkOrderChecklistItem item : items) {
                if (Boolean.TRUE.equals(item.getIsMandatory()) && !item.isCompleted()) {
                    throw new IllegalArgumentException(
                            "Không thể hoàn thành: Chưa hoàn thành bước bắt buộc '" + item.getItemName() + "'");
                }
            }

            workOrder.setCompletedAt(ZonedDateTime.now());
        }

        if (newStatus == WorkOrderStatus.CANCELED) {
            if (currentStatus == WorkOrderStatus.COMPLETED) {
                throw new IllegalArgumentException("Cannot cancel a COMPLETED Work Order");
            }
            // Supervisor or assignee check if needed, but assuming controller PreAuthorize
            // handles it
        }

        workOrder.setStatus(newStatus);
        workOrder.setUpdatedBy(currentUserId);
        WorkOrder savedWorkOrder = workOrderRepository.save(workOrder);

        auditLogService.logAction(
                com.eam.api.models.enums.ActionType.UPDATE,
                "WorkOrder",
                savedWorkOrder.getId().toString());

        if (newStatus == WorkOrderStatus.COMPLETED) {
            Map<String, Object> payload = new HashMap<>();
            payload.put("workOrderId", savedWorkOrder.getId());
            payload.put("tenantId", tenantId);
            try {
                kafkaTemplate.send("work_orders_topic", "work_order.completed",
                        objectMapper.writeValueAsString(payload));
            } catch (Exception e) {
                throw new RuntimeException("Failed to serialize Kafka event payload", e);
            }
        }

        return mapToDto(savedWorkOrder);
    }

    @Transactional
    public WorkOrderChecklistDto updateChecklist(UUID workOrderId, WorkOrderChecklistItemRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(workOrderId, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        UUID currentUserId = getCurrentUserId();
        checkUpdatePermission(workOrder, currentUserId);

        // Find existing or create new
        com.eam.api.repositories.WorkOrderChecklistRepository checklistRepo = getChecklistRepository();

        // Let's just create a new one for simplicity if not found, or maybe we just add
        // new items?
        // Wait, the UI might send updates to existing. But the request only has
        // itemName and isCompleted.
        // It's better to just add a new item or find by itemName.
        java.util.List<com.eam.api.models.entities.WorkOrderChecklistItem> items = checklistRepo
                .findByWorkOrderIdOrderByCreatedAtAsc(workOrderId);
        com.eam.api.models.entities.WorkOrderChecklistItem item = items.stream()
                .filter(i -> i.getItemName().equals(request.getItemName()))
                .findFirst()
                .orElseGet(() -> {
                    com.eam.api.models.entities.WorkOrderChecklistItem newItem = new com.eam.api.models.entities.WorkOrderChecklistItem();
                    newItem.setTenantId(tenantId);
                    newItem.setWorkOrder(workOrder);
                    newItem.setItemName(request.getItemName());
                    newItem.setCreatedBy(currentUserId);
                    return newItem;
                });

        item.setCompleted(request.getIsCompleted());
        if (request.getActualValue() != null) {
            item.setActualValue(request.getActualValue());
        }
        item.setUpdatedBy(currentUserId);
        com.eam.api.models.entities.WorkOrderChecklistItem savedItem = checklistRepo.save(item);

        return mapChecklistToDto(savedItem);
    }

    @Transactional
    public WorkOrderDto updateNotes(UUID workOrderId, com.eam.api.models.dtos.WorkOrderNoteUpdateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(workOrderId, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        UUID currentUserId = getCurrentUserId();
        checkUpdatePermission(workOrder, currentUserId);

        workOrder.setResolutionNotes(request.getResolutionNotes());
        workOrder.setUpdatedBy(currentUserId);
        return mapToDto(workOrderRepository.save(workOrder));
    }

    @Transactional
    public WorkOrderAttachmentDto uploadAttachment(UUID workOrderId,
            org.springframework.web.multipart.MultipartFile file) throws Exception {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(workOrderId, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        UUID currentUserId = getCurrentUserId();
        checkUpdatePermission(workOrder, currentUserId);

        // Validate type and size (NFR12)
        if (file.isEmpty()) {
            throw new IllegalArgumentException("File cannot be empty");
        }
        if (file.getSize() > 5 * 1024 * 1024) { // 5MB limit
            throw new IllegalArgumentException("File size exceeds 5MB limit");
        }
        String contentType = file.getContentType();
        if (contentType == null || !contentType.startsWith("image/")) {
            throw new IllegalArgumentException("Only image files are allowed");
        }

        String folder = "tenant-" + tenantId + "/work-orders/" + workOrderId;
        String fileUrl = fileStorageService.uploadFile(file, folder);

        com.eam.api.models.entities.WorkOrderAttachment attachment = new com.eam.api.models.entities.WorkOrderAttachment();
        attachment.setTenantId(tenantId);
        attachment.setWorkOrder(workOrder);
        attachment.setFileUrl(fileUrl);
        attachment.setFileName(file.getOriginalFilename());
        attachment.setFileType(contentType);
        attachment.setFileSize(file.getSize());
        attachment.setCreatedBy(currentUserId);
        attachment.setUpdatedBy(currentUserId);

        com.eam.api.repositories.WorkOrderAttachmentRepository attachmentRepo = getAttachmentRepository();
        com.eam.api.models.entities.WorkOrderAttachment savedAttachment = attachmentRepo.save(attachment);

        return mapAttachmentToDto(savedAttachment);
    }

    private void checkUpdatePermission(WorkOrder workOrder, UUID currentUserId) {
        if (!currentUserId.equals(workOrder.getAssignedTo())) {
            // Need to check if supervisor (has work_order:update)
            User user = userRepository.findById(currentUserId).orElse(null);
            boolean isSupervisor = user != null && user.getRoles().stream()
                    .flatMap(r -> r.getPermissions().stream())
                    .anyMatch(p -> "work_order:update".equals(p.getId()));
            if (!isSupervisor) {
                throw new IllegalArgumentException("Only the assignee or supervisor can update this Work Order");
            }
        }
    }

    @org.springframework.beans.factory.annotation.Autowired
    private org.springframework.context.ApplicationContext context;

    private com.eam.api.repositories.WorkOrderChecklistRepository getChecklistRepository() {
        return context.getBean(com.eam.api.repositories.WorkOrderChecklistRepository.class);
    }

    private com.eam.api.repositories.WorkOrderAttachmentRepository getAttachmentRepository() {
        return context.getBean(com.eam.api.repositories.WorkOrderAttachmentRepository.class);
    }

    private WorkOrderChecklistDto mapChecklistToDto(com.eam.api.models.entities.WorkOrderChecklistItem item) {
        WorkOrderChecklistDto dto = new WorkOrderChecklistDto();
        dto.setId(item.getId());
        dto.setItemName(item.getItemName());
        dto.setCompleted(item.isCompleted());
        dto.setInputType(item.getInputType());
        dto.setExpectedValue(item.getExpectedValue());
        dto.setActualValue(item.getActualValue());
        dto.setIsMandatory(item.getIsMandatory());
        dto.setCreatedAt(item.getCreatedAt());
        dto.setUpdatedAt(item.getUpdatedAt());
        return dto;
    }

    private com.eam.api.models.dtos.WorkOrderAttachmentDto mapAttachmentToDto(
            com.eam.api.models.entities.WorkOrderAttachment attachment) {
        com.eam.api.models.dtos.WorkOrderAttachmentDto dto = new com.eam.api.models.dtos.WorkOrderAttachmentDto();
        dto.setId(attachment.getId());
        dto.setFileUrl(attachment.getFileUrl());
        dto.setFileName(attachment.getFileName());
        dto.setFileType(attachment.getFileType());
        dto.setFileSize(attachment.getFileSize());
        dto.setCreatedAt(attachment.getCreatedAt());
        dto.setUpdatedAt(attachment.getUpdatedAt());
        return dto;
    }

    private com.eam.api.models.dtos.WorkOrderMaterialDto mapMaterialToDto(
            com.eam.api.models.entities.WorkOrderMaterial material) {
        com.eam.api.models.dtos.WorkOrderMaterialDto dto = new com.eam.api.models.dtos.WorkOrderMaterialDto();
        dto.setId(material.getId());
        dto.setQuantity(material.getQuantity());
        dto.setActualCost(material.getActualCost());
        if (material.getSparePart() != null) {
            com.eam.api.models.dtos.SparePartDto partDto = new com.eam.api.models.dtos.SparePartDto();
            partDto.setId(material.getSparePart().getId());
            partDto.setName(material.getSparePart().getName());
            partDto.setPartNumber(material.getSparePart().getPartNumber());
            dto.setSparePart(partDto);
        }
        return dto;
    }

    private UUID getCurrentUserId() {
        if (SecurityContextHolder.getContext().getAuthentication() != null) {
            Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
            if (principal instanceof CustomUserDetails) {
                return ((CustomUserDetails) principal).getId();
            }
        }
        return null;
    }

    @Transactional
    public void deleteChecklist(UUID workOrderId, UUID checklistId) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(workOrderId, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        UUID currentUserId = getCurrentUserId();
        checkUpdatePermission(workOrder, currentUserId);

        com.eam.api.models.entities.WorkOrderChecklistItem item = getChecklistRepository().findById(checklistId)
                .orElseThrow(() -> new IllegalArgumentException("Checklist item not found"));

        if (Boolean.TRUE.equals(item.getIsMandatory())) {
            User user = userRepository.findById(currentUserId).orElse(null);
            boolean isSupervisor = user != null && user.getRoles().stream()
                    .flatMap(r -> r.getPermissions().stream())
                    .anyMatch(p -> "work_order:update".equals(p.getId()));
            if (!isSupervisor) {
                throw new IllegalArgumentException("Kỹ thuật viên không được phép xóa hạng mục công việc bắt buộc");
            }
        }

        getChecklistRepository().deleteById(checklistId);
    }

    @Transactional
    public void deleteAttachment(UUID workOrderId, UUID attachmentId) {
        String tenantId = TenantContext.getCurrentTenant();
        WorkOrder workOrder = workOrderRepository.findByIdAndTenantId(workOrderId, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Work Order not found"));

        UUID currentUserId = getCurrentUserId();
        checkUpdatePermission(workOrder, currentUserId);

        getAttachmentRepository().deleteById(attachmentId);
    }

    private WorkOrderDto mapToDto(WorkOrder workOrder) {
        WorkOrderDto dto = new WorkOrderDto();
        dto.setId(workOrder.getId());
        dto.setTitle(workOrder.getTitle());
        dto.setDescription(workOrder.getDescription());
        dto.setPriority(workOrder.getPriority());
        dto.setStatus(workOrder.getStatus());
        dto.setDeadline(workOrder.getDeadline());
        dto.setAssignedAt(workOrder.getAssignedAt());
        dto.setActualStartTime(workOrder.getActualStartTime());
        dto.setCompletedAt(workOrder.getCompletedAt());
        dto.setCreatedAt(workOrder.getCreatedAt());
        dto.setUpdatedAt(workOrder.getUpdatedAt());
        dto.setEstimatedDurationMinutes(workOrder.getEstimatedDurationMinutes());
        dto.setActualDurationMinutes(workOrder.getActualDurationMinutes());

        dto.setResolutionNotes(workOrder.getResolutionNotes());

        if (workOrder.getParentWorkOrder() != null) {
            com.eam.api.models.dtos.WorkOrderReferenceDto ref = new com.eam.api.models.dtos.WorkOrderReferenceDto();
            ref.setId(workOrder.getParentWorkOrder().getId());
            ref.setTitle(workOrder.getParentWorkOrder().getTitle());
            ref.setStatus(workOrder.getParentWorkOrder().getStatus());
            dto.setParentWorkOrder(ref);
        }

        if (context != null) {
            java.util.List<com.eam.api.models.entities.WorkOrderChecklistItem> items = getChecklistRepository()
                    .findByWorkOrderIdOrderByCreatedAtAsc(workOrder.getId());
            dto.setChecklists(
                    items.stream().map(this::mapChecklistToDto).collect(java.util.stream.Collectors.toList()));

            java.util.List<com.eam.api.models.entities.WorkOrderAttachment> attachments = getAttachmentRepository()
                    .findByWorkOrderIdOrderByCreatedAtAsc(workOrder.getId());
            dto.setAttachments(
                    attachments.stream().map(this::mapAttachmentToDto).collect(java.util.stream.Collectors.toList()));

            com.eam.api.repositories.WorkOrderMaterialRepository materialRepo = context
                    .getBean(com.eam.api.repositories.WorkOrderMaterialRepository.class);
            java.util.List<com.eam.api.models.entities.WorkOrderMaterial> materials = materialRepo
                    .findByWorkOrderId(workOrder.getId());
            if (materials != null) {
                dto.setMaterials(
                        materials.stream().map(this::mapMaterialToDto).collect(java.util.stream.Collectors.toList()));
            }
        }

        java.util.List<WorkOrder> followUps = workOrder.getFollowUpWorkOrders();
        if (followUps != null && !followUps.isEmpty()) {
            dto.setFollowUpWorkOrders(followUps.stream().map(fw -> {
                com.eam.api.models.dtos.WorkOrderReferenceDto ref = new com.eam.api.models.dtos.WorkOrderReferenceDto();
                ref.setId(fw.getId());
                ref.setTitle(fw.getTitle());
                ref.setStatus(fw.getStatus());
                return ref;
            }).collect(java.util.stream.Collectors.toList()));
        }

        if (workOrder.getCreator() != null) {
            UserDto creatorDto = new UserDto();
            creatorDto.setId(workOrder.getCreator().getId());
            creatorDto.setUsername(workOrder.getCreator().getUsername());
            creatorDto.setEmail(workOrder.getCreator().getEmail());
            dto.setCreator(creatorDto);
        }

        if (workOrder.getAssignee() != null) {
            UserDto assigneeDto = new UserDto();
            assigneeDto.setId(workOrder.getAssignee().getId());
            assigneeDto.setUsername(workOrder.getAssignee().getUsername());
            assigneeDto.setEmail(workOrder.getAssignee().getEmail());
            dto.setAssignee(assigneeDto);
        }

        if (workOrder.getAsset() != null) {
            Asset asset = workOrder.getAsset();
            dto.setAsset(new AssetResponse(
                    asset.getId(),
                    asset.getName(),
                    asset.getCategory() != null ? asset.getCategory().getId() : null,
                    asset.getCategory() != null ? asset.getCategory().getName() : null,
                    asset.getParentId(),
                    asset.getSerialNumber(),
                    asset.getModel(),
                    asset.getManufacturer(),
                    asset.getPurchaseDate(),
                    asset.getValue(),
                    asset.getStatus(),
                    asset.getLocation() != null ? asset.getLocation().getId() : null,
                    asset.getLocation() != null ? asset.getLocation().getName() : null,
                    asset.getHierarchyTemplate() != null ? asset.getHierarchyTemplate().getId() : null,
                    asset.getHierarchyTemplate() != null ? asset.getHierarchyTemplate().getName() : null,
                    asset.getQrCode(),
                    asset.getIsActive(),
                    asset.getCreatedAt(),
                    asset.getUpdatedAt(),
                    asset.getCreator() != null ? asset.getCreator().getUsername() : null,
                    asset.getUpdater() != null ? asset.getUpdater().getUsername() : null));
        }

        return dto;
    }
}
