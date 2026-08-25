package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.entities.Permission;
import com.eam.api.models.entities.Role;
import com.eam.api.repositories.PermissionRepository;
import com.eam.api.repositories.RoleRepository;
import com.eam.api.repositories.UserRepository;
import com.eam.api.models.entities.User;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

@Service
public class RoleService {

    private final RoleRepository roleRepository;
    private final PermissionRepository permissionRepository;
    private final UserRepository userRepository;

    public RoleService(RoleRepository roleRepository, PermissionRepository permissionRepository,
            UserRepository userRepository) {
        this.roleRepository = roleRepository;
        this.permissionRepository = permissionRepository;
        this.userRepository = userRepository;
    }

    public List<Role> getAllRoles() {
        String tenantId = TenantContext.getCurrentTenant();
        List<Role> roles = roleRepository.findByTenantId(tenantId);

        org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder
                .getContext().getAuthentication();
        boolean isSuperAdmin = auth != null
                && auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_SUPER_ADMIN"));

        if (!isSuperAdmin) {
            return roles.stream().filter(r -> !"SUPER_ADMIN".equals(r.getName())).toList();
        }
        return roles;
    }

    public List<Permission> getAllPermissions() {
        return permissionRepository.findAll().stream()
                .filter(p -> !"system:admin".equals(p.getId()))
                .toList();
    }

    @Transactional
    public Role createRole(String name, String description, List<String> permissionIds) {
        String tenantId = TenantContext.getCurrentTenant();

        if (roleRepository.findByNameAndTenantId(name, tenantId).isPresent()) {
            throw new IllegalArgumentException("Role with name " + name + " already exists in this tenant");
        }

        Role role = new Role();
        role.setTenantId(tenantId);
        role.setName(name);
        role.setDescription(description);
        role.setIsSystem(false);

        Set<Permission> permissions = new HashSet<>(permissionRepository.findAllById(permissionIds));
        role.setPermissions(permissions);

        return roleRepository.save(role);
    }

    @Transactional
    public Role updateRole(UUID roleId, String name, String description, List<String> permissionIds) {
        String tenantId = TenantContext.getCurrentTenant();

        Role role = roleRepository.findById(roleId)
                .orElseThrow(() -> new IllegalArgumentException("Role not found"));

        if (!role.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("Role not found in this tenant");
        }

        if (role.getIsSystem()) {
            throw new IllegalArgumentException("Cannot update system role");
        }

        role.setName(name);
        role.setDescription(description);

        Set<Permission> permissions = new HashSet<>(permissionRepository.findAllById(permissionIds));
        role.setPermissions(permissions);

        return roleRepository.save(role);
    }

    @Transactional
    public void deleteRole(UUID roleId, UUID fallbackRoleId) {
        String tenantId = TenantContext.getCurrentTenant();

        Role role = roleRepository.findById(roleId)
                .orElseThrow(() -> new IllegalArgumentException("Role not found"));

        if (!role.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("Role not found in this tenant");
        }

        if (role.getIsSystem()) {
            throw new IllegalArgumentException("Cannot delete system role");
        }

        List<User> usersWithRole = userRepository.findByRolesIdAndTenantId(roleId, tenantId);
        if (!usersWithRole.isEmpty()) {
            if (fallbackRoleId == null) {
                throw new IllegalArgumentException("ROLE_HAS_USERS");
            }

            Role fallbackRole = roleRepository.findById(fallbackRoleId)
                    .orElseThrow(() -> new IllegalArgumentException("Fallback role not found"));

            if (!fallbackRole.getTenantId().equals(tenantId)) {
                throw new IllegalArgumentException("Fallback role not found in this tenant");
            }

            for (User user : usersWithRole) {
                user.getRoles().remove(role);
                user.getRoles().add(fallbackRole);
                userRepository.save(user);
            }
        }

        roleRepository.delete(role);
    }
}
