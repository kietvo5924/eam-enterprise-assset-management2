package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.entities.Tenant;
import com.eam.api.models.entities.User;
import com.eam.api.models.dtos.SystemTenantAdminRequest;
import com.eam.api.models.dtos.SystemTenantCreateRequest;
import com.eam.api.services.SystemTenantService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/system/tenants")
@PreAuthorize("hasAuthority('system:admin')")
public class SystemTenantController {

    @Autowired
    private SystemTenantService systemTenantService;

    @GetMapping
    public ResponseEntity<ApiResponse<List<Tenant>>> getAllTenants() {
        List<Tenant> tenants = systemTenantService.getAllTenants();
        return ResponseEntity.ok(ApiResponse.success(tenants));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<Tenant>> createTenant(@Valid @RequestBody SystemTenantCreateRequest request) {
        Tenant tenant = systemTenantService.createTenant(request);
        return ResponseEntity.ok(ApiResponse.success(tenant));
    }

    @PostMapping("/{tenantId}/admins")
    public ResponseEntity<ApiResponse<User>> createTenantAdmin(
            @PathVariable UUID tenantId,
            @Valid @RequestBody SystemTenantAdminRequest request) {
        User user = systemTenantService.createTenantAdmin(tenantId, request);
        return ResponseEntity.ok(ApiResponse.success(user));
    }

    @GetMapping("/{tenantId}/admins")
    public ResponseEntity<ApiResponse<List<User>>> getTenantAdmins(@PathVariable UUID tenantId) {
        List<User> admins = systemTenantService.getTenantAdmins(tenantId);
        return ResponseEntity.ok(ApiResponse.success(admins));
    }

    @PutMapping("/{tenantId}")
    public ResponseEntity<ApiResponse<Tenant>> updateTenant(
            @PathVariable UUID tenantId,
            @RequestBody java.util.Map<String, String> body) {
        Tenant tenant = systemTenantService.updateTenant(tenantId, body.get("name"), body.get("servicePlan"));
        return ResponseEntity.ok(ApiResponse.success(tenant));
    }

    @PutMapping("/{tenantId}/status")
    public ResponseEntity<ApiResponse<Tenant>> updateTenantStatus(
            @PathVariable UUID tenantId,
            @RequestBody java.util.Map<String, String> body) {
        Tenant tenant = systemTenantService.updateTenantStatus(tenantId, body.get("status"));
        return ResponseEntity.ok(ApiResponse.success(tenant));
    }

    @PutMapping("/{tenantId}/admins/{adminId}")
    public ResponseEntity<ApiResponse<User>> updateAdmin(
            @PathVariable UUID tenantId,
            @PathVariable UUID adminId,
            @RequestBody java.util.Map<String, String> body) {
        User user = systemTenantService.updateAdmin(adminId, body.get("username"), body.get("password"));
        return ResponseEntity.ok(ApiResponse.success(user));
    }

    @PutMapping("/{tenantId}/admins/{adminId}/status")
    public ResponseEntity<ApiResponse<User>> updateAdminStatus(
            @PathVariable UUID tenantId,
            @PathVariable UUID adminId,
            @RequestBody java.util.Map<String, String> body) {
        User user = systemTenantService.updateAdminStatus(adminId,
                com.eam.api.models.entities.UserStatus.valueOf(body.get("status")));
        return ResponseEntity.ok(ApiResponse.success(user));
    }
}
