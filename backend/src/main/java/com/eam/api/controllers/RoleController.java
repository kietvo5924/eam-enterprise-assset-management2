package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.entities.Permission;
import com.eam.api.models.entities.Role;
import com.eam.api.services.RoleService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
public class RoleController {

    private final RoleService roleService;

    public RoleController(RoleService roleService) {
        this.roleService = roleService;
    }

    @GetMapping("/roles")
    @PreAuthorize("hasAuthority('role:read')")
    public ApiResponse<List<Role>> getRoles() {
        return ApiResponse.success(roleService.getAllRoles());
    }

    @GetMapping("/permissions")
    @PreAuthorize("hasAuthority('role:read')")
    public ApiResponse<List<Permission>> getPermissions() {
        return ApiResponse.success(roleService.getAllPermissions());
    }

    @PostMapping("/roles")
    @PreAuthorize("hasAuthority('role:create')")
    public ApiResponse<Role> createRole(@RequestBody Map<String, Object> request) {
        String name = (String) request.get("name");
        String description = (String) request.get("description");
        List<String> permissionIds = (List<String>) request.get("permissionIds");

        return ApiResponse.success(roleService.createRole(name, description, permissionIds));
    }

    @PutMapping("/roles/{id}")
    @PreAuthorize("hasAuthority('role:update')")
    public ApiResponse<Role> updateRole(@PathVariable UUID id, @RequestBody Map<String, Object> request) {
        String name = (String) request.get("name");
        String description = (String) request.get("description");
        List<String> permissionIds = (List<String>) request.get("permissionIds");

        return ApiResponse.success(roleService.updateRole(id, name, description, permissionIds));
    }

    @DeleteMapping("/roles/{id}")
    @PreAuthorize("hasAuthority('role:delete')")
    public ApiResponse<Void> deleteRole(@PathVariable UUID id, @RequestParam(required = false) UUID fallbackRoleId) {
        roleService.deleteRole(id, fallbackRoleId);
        return ApiResponse.success(null);
    }
}
