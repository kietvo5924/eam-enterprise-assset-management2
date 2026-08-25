package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.WorkOrderCreateRequest;
import com.eam.api.models.dtos.WorkOrderAssignRequest;
import com.eam.api.models.dtos.WorkOrderDto;
import com.eam.api.models.dtos.WorkOrderStatusUpdateRequest;
import com.eam.api.services.WorkOrderService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.time.ZonedDateTime;
import java.util.List;
import java.util.UUID;
import org.springframework.format.annotation.DateTimeFormat;
import com.eam.api.models.dtos.MaintenanceCalendarEventDto;

@RestController
@RequestMapping("/api/v1/work-orders")
public class WorkOrderController {

    private final WorkOrderService workOrderService;

    public WorkOrderController(WorkOrderService workOrderService) {
        this.workOrderService = workOrderService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('work_order:read')")
    public ApiResponse<Page<WorkOrderDto>> getWorkOrders(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) int size) {
        return ApiResponse.success(workOrderService.getWorkOrders(PageRequest.of(page, size)));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAuthority('work_order:read')")
    public ApiResponse<WorkOrderDto> getWorkOrder(@PathVariable UUID id) {
        return ApiResponse.success(workOrderService.getWorkOrderById(id));
    }

    @GetMapping("/kpis")
    @PreAuthorize("hasAuthority('work_order:read')")
    public ApiResponse<com.eam.api.models.dtos.WorkOrderKpiDto> getWorkOrderKpis() {
        return ApiResponse.success(workOrderService.getWorkOrderKpis());
    }

    @GetMapping("/calendar")
    @PreAuthorize("hasAuthority('work_order:read')")
    public ApiResponse<List<MaintenanceCalendarEventDto>> getCalendarEvents(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) ZonedDateTime startDate,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) ZonedDateTime endDate,
            @RequestParam(required = false) UUID assetId,
            @RequestParam(required = false) UUID categoryId,
            @RequestParam(required = false) String status) {
        return ApiResponse.success(workOrderService.getCalendarEvents(startDate, endDate, assetId, categoryId, status));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAuthority('work_order:create')")
    public ApiResponse<WorkOrderDto> createWorkOrder(@Valid @RequestBody WorkOrderCreateRequest request) {
        return ApiResponse.success(workOrderService.createWorkOrder(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAuthority('work_order:update')")
    public ApiResponse<WorkOrderDto> updateWorkOrder(@PathVariable UUID id, @Valid @RequestBody WorkOrderCreateRequest request) {
        return ApiResponse.success(workOrderService.updateWorkOrder(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('work_order:delete')")
    public ApiResponse<Void> deleteWorkOrder(@PathVariable UUID id) {
        workOrderService.deleteWorkOrder(id);
        return ApiResponse.success(null);
    }

    @PutMapping("/{id}/assign")
    @PreAuthorize("hasAuthority('work_order:update')")
    public ApiResponse<WorkOrderDto> assignWorkOrder(@PathVariable UUID id, @Valid @RequestBody WorkOrderAssignRequest request) {
        return ApiResponse.success(workOrderService.assignWorkOrder(id, request));
    }

    @PutMapping("/{id}/status")
    @PreAuthorize("hasAnyAuthority('work_order:execute', 'work_order:update')")
    public ApiResponse<WorkOrderDto> updateWorkOrderStatus(@PathVariable UUID id, @Valid @RequestBody WorkOrderStatusUpdateRequest request) {
        return ApiResponse.success(workOrderService.updateWorkOrderStatus(id, request));
    }

    @PostMapping("/{id}/checklists")
    @PreAuthorize("hasAnyAuthority('work_order:execute', 'work_order:update')")
    public ApiResponse<com.eam.api.models.dtos.WorkOrderChecklistDto> updateChecklist(
            @PathVariable UUID id, 
            @Valid @RequestBody com.eam.api.models.dtos.WorkOrderChecklistItemRequest request) {
        return ApiResponse.success(workOrderService.updateChecklist(id, request));
    }

    @PutMapping("/{id}/notes")
    @PreAuthorize("hasAnyAuthority('work_order:execute', 'work_order:update')")
    public ApiResponse<WorkOrderDto> updateNotes(
            @PathVariable UUID id, 
            @Valid @RequestBody com.eam.api.models.dtos.WorkOrderNoteUpdateRequest request) {
        return ApiResponse.success(workOrderService.updateNotes(id, request));
    }

    @PostMapping("/{id}/attachments")
    @PreAuthorize("hasAnyAuthority('work_order:execute', 'work_order:update')")
    public ApiResponse<com.eam.api.models.dtos.WorkOrderAttachmentDto> uploadAttachment(
            @PathVariable UUID id, 
            @RequestParam("file") org.springframework.web.multipart.MultipartFile file) throws Exception {
        return ApiResponse.success(workOrderService.uploadAttachment(id, file));
    }

    @DeleteMapping("/{id}/checklists/{checklistId}")
    @PreAuthorize("hasAnyAuthority('work_order:execute', 'work_order:update')")
    public ApiResponse<Void> deleteChecklist(
            @PathVariable UUID id, 
            @PathVariable UUID checklistId) {
        workOrderService.deleteChecklist(id, checklistId);
        return ApiResponse.success(null);
    }

    @DeleteMapping("/{id}/attachments/{attachmentId}")
    @PreAuthorize("hasAnyAuthority('work_order:execute', 'work_order:update')")
    public ApiResponse<Void> deleteAttachment(
            @PathVariable UUID id, 
            @PathVariable UUID attachmentId) {
        workOrderService.deleteAttachment(id, attachmentId);
        return ApiResponse.success(null);
    }
}
