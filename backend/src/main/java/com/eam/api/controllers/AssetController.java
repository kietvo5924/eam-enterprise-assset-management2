package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.AssetCreateRequest;
import com.eam.api.models.dtos.AssetResponse;
import com.eam.api.models.dtos.AssetUpdateRequest;
import com.eam.api.services.AssetService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import jakarta.validation.constraints.Min;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/assets")
public class AssetController {

    private final AssetService assetService;
    private final com.eam.api.services.AssetImportExportService assetImportExportService;

    public AssetController(AssetService assetService, com.eam.api.services.AssetImportExportService assetImportExportService) {
        this.assetService = assetService;
        this.assetImportExportService = assetImportExportService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('asset:read')")
    public ApiResponse<Page<AssetResponse>> getAssets(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) int size) {
        return ApiResponse.success(assetService.getAssets(PageRequest.of(page, size)));
    }

    @GetMapping("/tree")
    @PreAuthorize("hasAuthority('asset:read')")
    public ApiResponse<com.eam.api.models.dtos.tree.AssetTreeResponse> getAssetTree(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) UUID categoryId) {
        return ApiResponse.success(assetService.getAssetTree(search, status, categoryId));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAuthority('asset:read')")
    public ApiResponse<AssetResponse> getAsset(@PathVariable UUID id) {
        return ApiResponse.success(assetService.getAssetById(id));
    }

    @GetMapping("/qr/{qrCode}")
    @PreAuthorize("hasAuthority('asset:read')")
    public ApiResponse<AssetResponse> getAssetByQrCode(@PathVariable String qrCode) {
        return ApiResponse.success(assetService.getAssetByQrCode(qrCode));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAuthority('asset:create')")
    public ApiResponse<AssetResponse> createAsset(@Valid @RequestBody AssetCreateRequest request) {
        return ApiResponse.success(assetService.createAsset(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAuthority('asset:update')")
    public ApiResponse<AssetResponse> updateAsset(
            @PathVariable UUID id, 
            @Valid @RequestBody AssetUpdateRequest request) {
        return ApiResponse.success(assetService.updateAsset(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('asset:delete')")
    public ApiResponse<Void> deleteAsset(@PathVariable UUID id) {
        assetService.deleteAsset(id);
        return ApiResponse.success(null);
    }

    @PostMapping("/import")
    @PreAuthorize("hasAuthority('asset:create')")
    public ApiResponse<com.eam.api.models.dtos.AssetImportResultDto> importAssets(@RequestParam("file") org.springframework.web.multipart.MultipartFile file) {
        return ApiResponse.success(assetImportExportService.importAssets(file));
    }

    @GetMapping("/export")
    @PreAuthorize("hasAuthority('asset:read')")
    public void exportAssets(jakarta.servlet.http.HttpServletResponse response) {
        assetImportExportService.exportAssets(response);
    }
}
