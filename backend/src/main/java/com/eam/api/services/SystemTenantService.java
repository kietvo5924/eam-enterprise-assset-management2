package com.eam.api.services;

import com.eam.api.models.entities.Role;
import com.eam.api.models.entities.Tenant;
import com.eam.api.models.entities.User;
import com.eam.api.models.dtos.SystemTenantAdminRequest;
import com.eam.api.models.dtos.SystemTenantCreateRequest;
import com.eam.api.repositories.RoleRepository;
import com.eam.api.repositories.TenantRepository;
import com.eam.api.repositories.UserRepository;
import com.eam.api.repositories.PermissionRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class SystemTenantService {

    @Autowired
    private TenantRepository tenantRepository;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private RoleRepository roleRepository;

    @Autowired
    private PermissionRepository permissionRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Transactional
    public Tenant createTenant(SystemTenantCreateRequest request) {
        if (tenantRepository.existsByTenantCode(request.getTenantCode())) {
            throw new IllegalArgumentException("Tenant code already exists");
        }

        Tenant tenant = new Tenant();
        tenant.setName(request.getName());
        tenant.setTenantCode(request.getTenantCode());
        tenant.setServicePlan(request.getServicePlan());
        tenant.setTimezone("UTC");

        return tenantRepository.save(tenant);
    }

    public List<Tenant> getAllTenants() {
        return tenantRepository.findAll();
    }

    @Transactional
    public User createTenantAdmin(UUID tenantId, SystemTenantAdminRequest request) {
        Tenant tenant = tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));

        String tenantIdStr = tenantId.toString();

        if (userRepository.existsByUsernameAndTenantId(request.getUsername(), tenantIdStr)) {
            throw new IllegalArgumentException("Username already exists in this tenant");
        }

        // Create TENANT_ADMIN role if not exists for this tenant
        Role adminRole = roleRepository.findByNameAndTenantId("TENANT_ADMIN", tenantIdStr)
                .orElseGet(() -> {
                    Role role = new Role();
                    role.setName("TENANT_ADMIN");
                    role.setDescription("Administrator for Tenant");
                    role.setIsSystem(true);
                    role.setTenantId(tenantIdStr);
                    // Fetch all available permissions except system:admin and assign them to the
                    // admin role
                    role.setPermissions(new java.util.HashSet<>(permissionRepository.findAll().stream()
                            .filter(p -> !"system:admin".equals(p.getId()))
                            .toList()));
                    return roleRepository.save(role);
                });

        User user = new User();
        user.setUsername(request.getUsername());
        user.setEmail(request.getUsername());
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        user.setTenantId(tenantIdStr);
        user.setStatus(com.eam.api.models.entities.UserStatus.ACTIVE);
        user.getRoles().add(adminRole);

        User savedUser = userRepository.save(user);

        // TODO: Send onboarding email here
        System.out.println("Sending onboarding email to " + request.getUsername() + " for tenant " + tenant.getName());

        return savedUser;
    }

    public List<User> getTenantAdmins(UUID tenantId) {
        String tenantIdStr = tenantId.toString();
        List<User> users = userRepository.findByTenantId(tenantIdStr);
        return users.stream()
                .filter(u -> u.getRoles().stream().anyMatch(r -> "TENANT_ADMIN".equals(r.getName())))
                .toList();
    }

    @Transactional
    public Tenant updateTenant(UUID tenantId, String name, String servicePlan) {
        Tenant tenant = tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));
        if (name != null)
            tenant.setName(name);
        if (servicePlan != null)
            tenant.setServicePlan(servicePlan);
        return tenantRepository.save(tenant);
    }

    @Transactional
    public Tenant updateTenantStatus(UUID tenantId, String status) {
        if ("00000000-0000-0000-0000-000000000000".equals(tenantId.toString())) {
            throw new IllegalArgumentException("Cannot block the System Administration tenant");
        }
        Tenant tenant = tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));
        tenant.setStatus(status);
        return tenantRepository.save(tenant);
    }

    @Transactional
    public User updateAdmin(UUID adminId, String username, String password) {
        User user = userRepository.findById(adminId)
                .orElseThrow(() -> new IllegalArgumentException("Admin not found"));
        if (username != null && !username.isEmpty()) {
            user.setUsername(username);
            user.setEmail(username);
        }
        if (password != null && !password.isEmpty()) {
            user.setPasswordHash(passwordEncoder.encode(password));
        }
        return userRepository.save(user);
    }

    @Transactional
    public User updateAdminStatus(UUID adminId, com.eam.api.models.entities.UserStatus status) {
        if ("00000000-0000-0000-0000-000000000000".equals(adminId.toString())) {
            throw new IllegalArgumentException("Cannot block the Super Admin");
        }
        User user = userRepository.findById(adminId)
                .orElseThrow(() -> new IllegalArgumentException("Admin not found"));
        user.setStatus(status);
        return userRepository.save(user);
    }
}
