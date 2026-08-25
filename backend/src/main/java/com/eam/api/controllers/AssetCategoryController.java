package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.AssetCategoryCreateRequest;
import com.eam.api.models.dtos.AssetCategoryDto;
import com.eam.api.models.dtos.AssetCategoryUpdateRequest;
import com.eam.api.services.AssetCategoryService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import jakarta.validation.constraints.Min;

@RestController
@RequestMapping("/api/v1/asset-categories")
public class AssetCategoryController {

    private final AssetCategoryService categoryService;

    public AssetCategoryController(AssetCategoryService categoryService) {
        this.categoryService = categoryService;
    }

    @GetMapping
    @PreAuthorize("hasAnyAuthority('asset_category:read', 'asset:read')")
    public ApiResponse<Page<AssetCategoryDto>> getCategories(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) int size) {
        return ApiResponse.success(categoryService.getCategories(PageRequest.of(page, size)));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAnyAuthority('asset_category:read', 'asset:read')")
    public ApiResponse<AssetCategoryDto> getCategory(@PathVariable UUID id) {
        return ApiResponse.success(categoryService.getCategoryById(id));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAuthority('asset_category:create')")
    public ApiResponse<AssetCategoryDto> createCategory(@Valid @RequestBody AssetCategoryCreateRequest request) {
        return ApiResponse.success(categoryService.createCategory(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAuthority('asset_category:update')")
    public ApiResponse<AssetCategoryDto> updateCategory(
            @PathVariable UUID id, 
            @Valid @RequestBody AssetCategoryUpdateRequest request) {
        return ApiResponse.success(categoryService.updateCategory(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('asset_category:delete')")
    public ApiResponse<Void> deleteCategory(@PathVariable UUID id) {
        categoryService.deleteCategory(id);
        return ApiResponse.success(null);
    }
}
