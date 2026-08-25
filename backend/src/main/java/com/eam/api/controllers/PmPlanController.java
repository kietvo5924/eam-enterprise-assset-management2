package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.PmPlanCreateRequest;
import com.eam.api.models.dtos.PmPlanDto;
import com.eam.api.models.dtos.PmPlanUpdateRequest;
import com.eam.api.models.dtos.AssignPmPlanRequest;
import com.eam.api.services.PmPlanService;
import jakarta.validation.Valid;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/pm-plans")
public class PmPlanController {

    private final PmPlanService pmPlanService;

    public PmPlanController(PmPlanService pmPlanService) {
        this.pmPlanService = pmPlanService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('pm_plan:read')")
    public ApiResponse<List<PmPlanDto>> getAllPmPlans() {
        return ApiResponse.success(pmPlanService.getAllPmPlans());
    }

    @GetMapping("/kpis")
    @PreAuthorize("hasAuthority('pm_plan:read')")
    public ApiResponse<com.eam.api.models.dtos.MaintenanceKpiDto> getMaintenanceKpis() {
        return ApiResponse.success(pmPlanService.getMaintenanceKpis());
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAuthority('pm_plan:read')")
    public ApiResponse<PmPlanDto> getPmPlanById(@PathVariable UUID id) {
        return ApiResponse.success(pmPlanService.getPmPlanById(id));
    }

    @PostMapping
    @PreAuthorize("hasAuthority('pm_plan:create')")
    public ApiResponse<PmPlanDto> createPmPlan(@Valid @RequestBody PmPlanCreateRequest request) {
        return ApiResponse.success(pmPlanService.createPmPlan(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAuthority('pm_plan:update')")
    public ApiResponse<PmPlanDto> updatePmPlan(
            @PathVariable UUID id,
            @Valid @RequestBody PmPlanUpdateRequest request) {
        return ApiResponse.success(pmPlanService.updatePmPlan(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('pm_plan:delete')")
    public ApiResponse<Void> deletePmPlan(@PathVariable UUID id) {
        pmPlanService.deletePmPlan(id);
        return ApiResponse.success(null);
    }

    @PostMapping("/{id}/assign")
    @PreAuthorize("hasAuthority('pm_plan:update')")
    public ApiResponse<Void> assignPmPlanToAssets(
            @PathVariable UUID id,
            @Valid @RequestBody AssignPmPlanRequest request) {
        pmPlanService.assignPmPlanToAssets(id, request);
        return ApiResponse.success(null);
    }

    @GetMapping("/{id}/assignments")
    @PreAuthorize("hasAuthority('pm_plan:read')")
    public ApiResponse<List<com.eam.api.models.dtos.PmPlanAssignmentDto>> getAssignments(@PathVariable UUID id) {
        return ApiResponse.success(pmPlanService.getAssignmentsByPlanId(id));
    }

    @DeleteMapping("/assignments/{assignmentId}")
    @PreAuthorize("hasAuthority('pm_plan:update')")
    public ApiResponse<Void> deleteAssignment(@PathVariable UUID assignmentId) {
        pmPlanService.deleteAssignment(assignmentId);
        return ApiResponse.success(null);
    }

    @PatchMapping("/assignments/{assignmentId}/status")
    @PreAuthorize("hasAuthority('pm_plan:update')")
    public ApiResponse<com.eam.api.models.dtos.PmPlanAssignmentDto> updateAssignmentStatus(
            @PathVariable UUID assignmentId,
            @Valid @RequestBody com.eam.api.models.dtos.PmAssignmentStatusUpdateRequest request) {
        return ApiResponse.success(pmPlanService.updateAssignmentStatus(assignmentId, request.getStatus()));
    }
}
