package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.PmPlanCreateRequest;
import com.eam.api.models.dtos.PmPlanDto;
import com.eam.api.models.dtos.PmPlanUpdateRequest;
import com.eam.api.models.dtos.AssignPmPlanRequest;
import com.eam.api.models.dtos.PmPlanAssignmentDto;
import com.eam.api.models.entities.Asset;
import com.eam.api.models.entities.PmPlan;
import com.eam.api.models.entities.PmPlanAssignment;
import com.eam.api.repositories.AssetRepository;
import com.eam.api.repositories.PmPlanAssignmentRepository;
import com.eam.api.repositories.PmPlanRepository;
import com.eam.api.repositories.WorkOrderRepository;
import com.eam.api.models.dtos.MaintenanceKpiDto;
import com.eam.api.models.enums.WorkOrderStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import java.math.BigDecimal;

@Service
public class PmPlanService {

    private final PmPlanRepository pmPlanRepository;
    private final AssetRepository assetRepository;
    private final PmPlanAssignmentRepository pmPlanAssignmentRepository;
    private final WorkOrderRepository workOrderRepository;
    private final com.eam.api.repositories.PmPlanChecklistRepository pmPlanChecklistRepository;
    private final com.eam.api.repositories.PmPlanMaterialRepository pmPlanMaterialRepository;
    private final com.eam.api.repositories.SparePartRepository sparePartRepository;
    private final com.eam.api.repositories.UserRepository userRepository;

    public PmPlanService(PmPlanRepository pmPlanRepository,
                         AssetRepository assetRepository,
                         PmPlanAssignmentRepository pmPlanAssignmentRepository,
                         WorkOrderRepository workOrderRepository,
                         com.eam.api.repositories.PmPlanChecklistRepository pmPlanChecklistRepository,
                         com.eam.api.repositories.PmPlanMaterialRepository pmPlanMaterialRepository,
                         com.eam.api.repositories.SparePartRepository sparePartRepository,
                         com.eam.api.repositories.UserRepository userRepository) {
        this.pmPlanRepository = pmPlanRepository;
        this.assetRepository = assetRepository;
        this.pmPlanAssignmentRepository = pmPlanAssignmentRepository;
        this.workOrderRepository = workOrderRepository;
        this.pmPlanChecklistRepository = pmPlanChecklistRepository;
        this.pmPlanMaterialRepository = pmPlanMaterialRepository;
        this.sparePartRepository = sparePartRepository;
        this.userRepository = userRepository;
    }

    public List<PmPlanDto> getAllPmPlans() {
        return pmPlanRepository.findAll().stream()
                .map(this::mapToDto)
                .collect(Collectors.toList());
    }

    public PmPlanDto getPmPlanById(UUID id) {
        return pmPlanRepository.findById(id)
                .map(this::mapToDto)
                .orElseThrow(() -> new IllegalArgumentException("PM Plan not found"));
    }

    @Transactional(readOnly = true)
    public MaintenanceKpiDto getMaintenanceKpis() {
        String tenantId = TenantContext.getCurrentTenant();
        
        long totalPlans = pmPlanRepository.countByTenantId(tenantId);
        
        // Count Missed PMs
        java.util.List<WorkOrderStatus> inactiveStatuses = java.util.Arrays.asList(
            WorkOrderStatus.COMPLETED, 
            WorkOrderStatus.CANCELED
        );
        long missedPms = workOrderRepository.countMissedPmWorkOrdersByTenantId(tenantId, inactiveStatuses);
        
        // Calculate Compliance Rate
        long totalPmWorkOrders = workOrderRepository.countPmWorkOrdersByTenantId(tenantId);
        long completedPmWorkOrders = workOrderRepository.countCompletedPmWorkOrdersByTenantId(tenantId);
        
        double complianceRate = 100.0;
        if (totalPmWorkOrders > 0) {
            complianceRate = ((double) completedPmWorkOrders / totalPmWorkOrders) * 100.0;
        }
        
        MaintenanceKpiDto dto = new MaintenanceKpiDto();
        dto.setTotalPlans(totalPlans);
        dto.setUpcomingIn7Days(0); // This requires projection, returning 0 for now to avoid overhead
        dto.setMissedPms(missedPms);
        dto.setComplianceRate(complianceRate);
        
        return dto;
    }

    @Transactional
    public PmPlanDto createPmPlan(PmPlanCreateRequest request) {
        PmPlan plan = new PmPlan();
        plan.setTenantId(TenantContext.getCurrentTenant());
        plan.setName(request.getName());
        plan.setDescription(request.getDescription());
        plan.setTriggerType(request.getTriggerType());
        plan.setIntervalValue(request.getIntervalValue());
        plan.setIntervalUnit(request.getTriggerType() == com.eam.api.models.enums.PmTriggerType.TIME ? request.getIntervalUnit() : null);
        if (request.getIsFloatingSchedule() != null) {
            plan.setIsFloatingSchedule(request.getIsFloatingSchedule());
        }
        if (request.getSuppressIfPending() != null) {
            plan.setSuppressIfPending(request.getSuppressIfPending());
        }
        if (request.getIsActive() != null) {
            plan.setIsActive(request.getIsActive());
        }
        if (request.getLeadTimeDays() != null) {
            plan.setLeadTimeDays(request.getLeadTimeDays());
        }
        if (request.getEstimatedDurationMinutes() != null) {
            plan.setEstimatedDurationMinutes(request.getEstimatedDurationMinutes());
        }
        if (request.getAssigneeId() != null) {
            plan.setAssignee(userRepository.findById(request.getAssigneeId()).orElse(null));
        }

        UUID currentUserId = getCurrentUserId();
        if (currentUserId != null) {
            plan.setCreatedBy(currentUserId);
            plan.setUpdatedBy(currentUserId);
        }

        PmPlan saved = pmPlanRepository.save(plan);

        if (request.getChecklists() != null) {
            for (com.eam.api.models.dtos.PmPlanChecklistDto dto : request.getChecklists()) {
                com.eam.api.models.entities.PmPlanChecklistItem item = new com.eam.api.models.entities.PmPlanChecklistItem();
                item.setTenantId(saved.getTenantId());
                item.setPmPlan(saved);
                item.setItemName(dto.getItemName());
                item.setInputType(dto.getInputType() != null ? dto.getInputType() : "PASS_FAIL");
                item.setExpectedValue(dto.getExpectedValue());
                item.setIsMandatory(dto.getIsMandatory() != null ? dto.getIsMandatory() : false);
                pmPlanChecklistRepository.save(item);
            }
        }

        if (request.getMaterials() != null) {
            for (com.eam.api.models.dtos.PmPlanMaterialDto dto : request.getMaterials()) {
                java.util.Optional<com.eam.api.models.entities.SparePart> spOpt = sparePartRepository.findById(dto.getSparePartId());
                if (spOpt.isPresent()) {
                    com.eam.api.models.entities.PmPlanMaterial pm = new com.eam.api.models.entities.PmPlanMaterial();
                    pm.setTenantId(saved.getTenantId());
                    pm.setPmPlan(saved);
                    pm.setSparePart(spOpt.get());
                    pm.setQuantity(dto.getQuantity());
                    pmPlanMaterialRepository.save(pm);
                }
            }
        }

        return mapToDto(pmPlanRepository.findById(saved.getId()).get());
    }

    @Transactional
    public PmPlanDto updatePmPlan(UUID id, PmPlanUpdateRequest request) {
        PmPlan plan = pmPlanRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("PM Plan not found"));

        if (request.getName() != null) plan.setName(request.getName());
        if (request.getDescription() != null) plan.setDescription(request.getDescription());
        if (request.getTriggerType() != null) plan.setTriggerType(request.getTriggerType());
        if (request.getIntervalValue() != null) plan.setIntervalValue(request.getIntervalValue());
        
        if (plan.getTriggerType() == com.eam.api.models.enums.PmTriggerType.TIME) {
            if (request.getIntervalUnit() != null) plan.setIntervalUnit(request.getIntervalUnit());
        } else {
            plan.setIntervalUnit(null);
        }
        if (request.getIsFloatingSchedule() != null) {
            plan.setIsFloatingSchedule(request.getIsFloatingSchedule());
        }
        if (request.getSuppressIfPending() != null) {
            plan.setSuppressIfPending(request.getSuppressIfPending());
        }
        if (request.getIsActive() != null) plan.setIsActive(request.getIsActive());
        if (request.getLeadTimeDays() != null) plan.setLeadTimeDays(request.getLeadTimeDays());
        if (request.getEstimatedDurationMinutes() != null) plan.setEstimatedDurationMinutes(request.getEstimatedDurationMinutes());
        if (request.getAssigneeId() != null) {
            plan.setAssignee(userRepository.findById(request.getAssigneeId()).orElse(null));
        }

        UUID currentUserId = getCurrentUserId();
        if (currentUserId != null) {
            plan.setUpdatedBy(currentUserId);
        } else if (request.getAssigneeId() == null && request.getName() != null) {
            // Optional: If you want to allow unassigning, you'd need a separate flag or allow null.
            // For now, if it's passed as null, we just ignore unless we want to clear it. Let's just update if present.
        }

        PmPlan updated = pmPlanRepository.save(plan);

        if (request.getChecklists() != null) {
            List<com.eam.api.models.entities.PmPlanChecklistItem> existingChecklists = pmPlanChecklistRepository.findByPmPlanId(id);
            pmPlanChecklistRepository.deleteAll(existingChecklists);
            for (com.eam.api.models.dtos.PmPlanChecklistDto dto : request.getChecklists()) {
                com.eam.api.models.entities.PmPlanChecklistItem item = new com.eam.api.models.entities.PmPlanChecklistItem();
                item.setTenantId(updated.getTenantId());
                item.setPmPlan(updated);
                item.setItemName(dto.getItemName());
                item.setInputType(dto.getInputType() != null ? dto.getInputType() : "PASS_FAIL");
                item.setExpectedValue(dto.getExpectedValue());
                item.setIsMandatory(dto.getIsMandatory() != null ? dto.getIsMandatory() : false);
                pmPlanChecklistRepository.save(item);
            }
        }

        if (request.getMaterials() != null) {
            List<com.eam.api.models.entities.PmPlanMaterial> existingMaterials = pmPlanMaterialRepository.findByPmPlanId(id);
            pmPlanMaterialRepository.deleteAll(existingMaterials);
            for (com.eam.api.models.dtos.PmPlanMaterialDto dto : request.getMaterials()) {
                java.util.Optional<com.eam.api.models.entities.SparePart> spOpt = sparePartRepository.findById(dto.getSparePartId());
                if (spOpt.isPresent()) {
                    com.eam.api.models.entities.PmPlanMaterial pm = new com.eam.api.models.entities.PmPlanMaterial();
                    pm.setTenantId(updated.getTenantId());
                    pm.setPmPlan(updated);
                    pm.setSparePart(spOpt.get());
                    pm.setQuantity(dto.getQuantity());
                    pmPlanMaterialRepository.save(pm);
                }
            }
        }

        return mapToDto(pmPlanRepository.findById(updated.getId()).get());
    }

    @Transactional
    public void deletePmPlan(UUID id) {
        PmPlan plan = pmPlanRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("PM Plan not found"));
        
        boolean hasGeneratedWOs = workOrderRepository.existsBySourceReferenceStartingWith("PM_" + id + "_ASSET_");
        if (hasGeneratedWOs) {
            throw new IllegalArgumentException("Không thể xóa PM Plan này vì đã có Work Order được sinh ra từ nó. Vui lòng vô hiệu hóa (Deactivate) thay vì xóa.");
        }

        List<PmPlanAssignment> assignments = pmPlanAssignmentRepository.findByPmPlanId(id);
        pmPlanAssignmentRepository.deleteAll(assignments);
        
        pmPlanRepository.delete(plan);
    }

    @Transactional
    public void assignPmPlanToAssets(UUID pmPlanId, AssignPmPlanRequest request) {
        PmPlan plan = pmPlanRepository.findById(pmPlanId)
                .orElseThrow(() -> new IllegalArgumentException("PM Plan not found"));

        Set<UUID> uniqueAssetIds = request.getAssetIds().stream().collect(Collectors.toSet());
        List<Asset> assets = assetRepository.findAllById(uniqueAssetIds);

        if (assets.size() != uniqueAssetIds.size()) {
            throw new IllegalArgumentException("One or more assets could not be found.");
        }

        List<PmPlanAssignment> existingAssignments = pmPlanAssignmentRepository.findByPmPlanId(plan.getId());
        Set<UUID> existingAssetIds = existingAssignments.stream()
                .map(a -> a.getAsset().getId())
                .collect(Collectors.toSet());

        List<PmPlanAssignment> newAssignments = assets.stream()
                .filter(asset -> {
                    if (!Objects.equals(plan.getTenantId(), asset.getTenantId())) {
                        throw new IllegalArgumentException("Asset " + asset.getId() + " does not belong to the same tenant as PM Plan.");
                    }
                    return !existingAssetIds.contains(asset.getId());
                })
                .map(asset -> {
                    PmPlanAssignment assignment = new PmPlanAssignment();
                    assignment.setTenantId(TenantContext.getCurrentTenant());
                    assignment.setPmPlan(plan);
                    assignment.setAsset(asset);
                    assignment.setStatus(com.eam.api.models.enums.PmAssignmentStatus.ACTIVE);
                    if (plan.getTriggerType() == com.eam.api.models.enums.PmTriggerType.METER) {
                        assignment.setBaselineMeterReading(BigDecimal.ZERO);
                    }
                    return assignment;
                })
                .collect(Collectors.toList());

        if (!newAssignments.isEmpty()) {
            pmPlanAssignmentRepository.saveAll(newAssignments);
        }
    }

    @Transactional(readOnly = true)
    public List<PmPlanAssignmentDto> getAssignmentsByPlanId(UUID pmPlanId) {
        return pmPlanAssignmentRepository.findByPmPlanId(pmPlanId).stream()
                .map(a -> {
                    PmPlanAssignmentDto dto = new PmPlanAssignmentDto();
                    dto.setId(a.getId());
                    dto.setPmPlanId(a.getPmPlan().getId());
                    dto.setAssetId(a.getAsset().getId());
                    dto.setAssetName(a.getAsset().getName());
                    dto.setBaselineMeterReading(a.getBaselineMeterReading());
                    dto.setStatus(a.getStatus());
                    return dto;
                })
                .collect(Collectors.toList());
    }

    @Transactional
    public void deleteAssignment(UUID assignmentId) {
        PmPlanAssignment assignment = pmPlanAssignmentRepository.findById(assignmentId)
            .orElseThrow(() -> new IllegalArgumentException("PM Plan Assignment not found"));

        String sourceReference = "PM_" + assignment.getPmPlan().getId() + "_ASSET_" + assignment.getAsset().getId();
        boolean hasGeneratedWOs = workOrderRepository.existsBySourceReference(sourceReference);

        if (hasGeneratedWOs) {
            throw new IllegalArgumentException("Cannot delete this assignment because Work Orders have already been generated. Please Pause or Deactivate instead.");
        }

        pmPlanAssignmentRepository.delete(assignment);
    }

    @Transactional
    public PmPlanAssignmentDto updateAssignmentStatus(UUID assignmentId, com.eam.api.models.enums.PmAssignmentStatus status) {
        PmPlanAssignment assignment = pmPlanAssignmentRepository.findById(assignmentId)
            .orElseThrow(() -> new IllegalArgumentException("PM Plan Assignment not found"));

        assignment.setStatus(status);
        PmPlanAssignment saved = pmPlanAssignmentRepository.save(assignment);

        PmPlanAssignmentDto dto = new PmPlanAssignmentDto();
        dto.setId(saved.getId());
        dto.setPmPlanId(saved.getPmPlan().getId());
        dto.setAssetId(saved.getAsset().getId());
        dto.setAssetName(saved.getAsset().getName());
        dto.setBaselineMeterReading(saved.getBaselineMeterReading());
        dto.setStatus(saved.getStatus());
        return dto;
    }

    public PmPlanDto mapToDto(PmPlan plan) {
        PmPlanDto dto = new PmPlanDto();
        dto.setId(plan.getId());
        dto.setName(plan.getName());
        dto.setDescription(plan.getDescription());
        dto.setTriggerType(plan.getTriggerType());
        dto.setIntervalValue(plan.getIntervalValue());
        dto.setIntervalUnit(plan.getIntervalUnit());
        dto.setIsActive(plan.getIsActive());
        dto.setIsFloatingSchedule(plan.getIsFloatingSchedule());
        dto.setSuppressIfPending(plan.getSuppressIfPending());
        dto.setLeadTimeDays(plan.getLeadTimeDays());
        dto.setEstimatedDurationMinutes(plan.getEstimatedDurationMinutes());
        
        if (plan.getAssignee() != null) {
            com.eam.api.models.dtos.UserDto userDto = new com.eam.api.models.dtos.UserDto();
            userDto.setId(plan.getAssignee().getId());
            userDto.setUsername(plan.getAssignee().getUsername());
            dto.setAssignee(userDto);
        }
        
        if (plan.getChecklists() != null) {
            dto.setChecklists(plan.getChecklists().stream().map(c -> {
                com.eam.api.models.dtos.PmPlanChecklistDto cdto = new com.eam.api.models.dtos.PmPlanChecklistDto();
                cdto.setId(c.getId());
                cdto.setItemName(c.getItemName());
                cdto.setInputType(c.getInputType());
                cdto.setExpectedValue(c.getExpectedValue());
                cdto.setIsMandatory(c.getIsMandatory());
                return cdto;
            }).collect(Collectors.toList()));
        }

        if (plan.getMaterials() != null) {
            dto.setMaterials(plan.getMaterials().stream().map(m -> {
                com.eam.api.models.dtos.PmPlanMaterialDto mdto = new com.eam.api.models.dtos.PmPlanMaterialDto();
                mdto.setId(m.getId());
                if (m.getSparePart() != null) {
                    mdto.setSparePartId(m.getSparePart().getId());
                    mdto.setSparePartName(m.getSparePart().getName());
                }
                mdto.setQuantity(m.getQuantity());
                return mdto;
            }).collect(Collectors.toList()));
        }

        dto.setCreatedAt(plan.getCreatedAt());
        dto.setUpdatedAt(plan.getUpdatedAt());
        return dto;
    }

    private UUID getCurrentUserId() {
        org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof com.eam.api.core.security.CustomUserDetails) {
            return ((com.eam.api.core.security.CustomUserDetails) auth.getPrincipal()).getId();
        }
        return null;
    }
}
