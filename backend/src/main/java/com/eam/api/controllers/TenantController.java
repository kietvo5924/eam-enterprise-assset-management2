package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.TenantSettingsDto;
import com.eam.api.services.TenantService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/tenant/settings")
public class TenantController {

    private final TenantService tenantService;

    public TenantController(TenantService tenantService) {
        this.tenantService = tenantService;
    }

    @GetMapping
    @org.springframework.security.access.prepost.PreAuthorize("hasAuthority('tenant:read')")
    public ResponseEntity<ApiResponse<TenantSettingsDto>> getSettings() {
        TenantSettingsDto settings = tenantService.getTenantSettings();
        ApiResponse<TenantSettingsDto> response = ApiResponse.success(settings);
        return ResponseEntity.ok(response);
    }

    @PutMapping
    @org.springframework.security.access.prepost.PreAuthorize("hasAuthority('tenant:update')")
    public ResponseEntity<ApiResponse<TenantSettingsDto>> updateSettings(
            @Valid @RequestBody TenantSettingsDto settingsDto) {
        TenantSettingsDto updatedSettings = tenantService.updateTenantSettings(settingsDto);
        ApiResponse<TenantSettingsDto> response = ApiResponse.success(updatedSettings);
        return ResponseEntity.ok(response);
    }
}
