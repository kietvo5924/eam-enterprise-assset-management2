package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.HierarchyTemplateCreateRequest;
import com.eam.api.models.dtos.HierarchyTemplateDto;
import com.eam.api.models.dtos.HierarchyTemplateUpdateRequest;
import com.eam.api.services.HierarchyTemplateService;
import jakarta.validation.Valid;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import jakarta.validation.constraints.Min;

@RestController
@RequestMapping("/api/v1/hierarchy-templates")
public class HierarchyTemplateController {

    private final HierarchyTemplateService templateService;

    public HierarchyTemplateController(HierarchyTemplateService templateService) {
        this.templateService = templateService;
    }

    @GetMapping
    @PreAuthorize("hasAnyAuthority('asset_category:read', 'asset:read')")
    public ApiResponse<Page<HierarchyTemplateDto>> getTemplates(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) int size) {
        return ApiResponse.success(templateService.getTemplates(PageRequest.of(page, size)));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAnyAuthority('asset_category:read', 'asset:read')")
    public ApiResponse<HierarchyTemplateDto> getTemplate(@PathVariable UUID id) {
        return ApiResponse.success(templateService.getTemplateById(id));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAuthority('asset_category:create')")
    public ApiResponse<HierarchyTemplateDto> createTemplate(
            @Valid @RequestBody HierarchyTemplateCreateRequest request) {
        return ApiResponse.success(templateService.createTemplate(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAuthority('asset_category:update')")
    public ApiResponse<HierarchyTemplateDto> updateTemplate(
            @PathVariable UUID id,
            @Valid @RequestBody HierarchyTemplateUpdateRequest request) {
        return ApiResponse.success(templateService.updateTemplate(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('asset_category:delete')")
    public ApiResponse<Void> deleteTemplate(@PathVariable UUID id) {
        templateService.deleteTemplate(id);
        return ApiResponse.success(null);
    }
}
