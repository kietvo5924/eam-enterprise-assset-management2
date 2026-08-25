package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.UserCreateRequest;
import com.eam.api.models.dtos.UserDto;
import com.eam.api.models.dtos.UserUpdateRequest;
import com.eam.api.models.dtos.UserInviteRequest;
import com.eam.api.models.entities.Role;
import com.eam.api.models.entities.User;
import com.eam.api.models.entities.UserStatus;
import com.eam.api.repositories.RoleRepository;
import com.eam.api.repositories.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class UserService {

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private RoleRepository roleRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private jakarta.persistence.EntityManager entityManager;

    @Autowired
    private EmailService emailService;

    @Transactional(readOnly = true)
    public Page<UserDto> getUsers(String roleName, String permissionId, Pageable pageable) {
        String tenantId = TenantContext.getCurrentTenant();
        if ("00000000-0000-0000-0000-000000000000".equals(tenantId)) {
            org.hibernate.Session session = entityManager.unwrap(org.hibernate.Session.class);
            session.disableFilter("tenantFilter");
            Page<UserDto> result;
            if (permissionId != null && !permissionId.isEmpty()) {
                result = userRepository
                        .findByRolesPermissionsIdExcludingSuperAdmin(permissionId,
                                java.util.UUID.fromString("00000000-0000-0000-0000-000000000000"), pageable)
                        .map(this::mapToDto);
            } else if (roleName != null && !roleName.isEmpty()) {
                result = userRepository
                        .findByRolesNameExcludingSuperAdmin(roleName,
                                java.util.UUID.fromString("00000000-0000-0000-0000-000000000000"), pageable)
                        .map(this::mapToDto);
            } else {
                result = userRepository
                        .findAllExcludingSuperAdmin(java.util.UUID.fromString("00000000-0000-0000-0000-000000000000"),
                                pageable)
                        .map(this::mapToDto);
            }
            session.enableFilter("tenantFilter").setParameter("tenantId", tenantId);
            return result;
        } else {
            if (permissionId != null && !permissionId.isEmpty()) {
                return userRepository.findByRolesPermissionsIdAndTenantId(permissionId, tenantId, pageable)
                        .map(this::mapToDto);
            }
            if (roleName != null && !roleName.isEmpty()) {
                return userRepository.findByRolesNameAndTenantId(roleName, tenantId, pageable).map(this::mapToDto);
            }
            return userRepository.findByTenantId(tenantId, pageable).map(this::mapToDto);
        }
    }

    @Transactional
    public UserDto createUser(UserCreateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();

        if (userRepository.existsByEmailAndTenantId(request.getEmail(), tenantId)) {
            throw new DataIntegrityViolationException("Email already exists in this tenant");
        }
        if (userRepository.existsByUsernameAndTenantId(request.getUsername(), tenantId)) {
            throw new DataIntegrityViolationException("Username already exists in this tenant");
        }

        User user = new User();
        user.setTenantId(tenantId);
        user.setUsername(request.getUsername());
        user.setEmail(request.getEmail());
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        user.setStatus(UserStatus.ACTIVE);

        if (request.getRoleIds() != null && !request.getRoleIds().isEmpty()) {
            org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder
                    .getContext().getAuthentication();
            boolean isSuperAdmin = auth != null
                    && auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_SUPER_ADMIN"));

            Set<Role> roles = new HashSet<>();
            for (UUID roleId : request.getRoleIds()) {
                Role role = roleRepository.findById(roleId)
                        .orElseThrow(() -> new IllegalArgumentException("Role not found"));
                if (!role.getTenantId().equals(tenantId)) {
                    throw new IllegalArgumentException("Invalid role for this tenant");
                }
                if ("SUPER_ADMIN".equals(role.getName()) && !isSuperAdmin) {
                    throw new IllegalArgumentException("You do not have permission to assign the SUPER_ADMIN role");
                }
                roles.add(role);
            }
            user.setRoles(roles);
        }

        user = userRepository.save(user);
        return mapToDto(user);
    }

    @Transactional
    public UserDto updateUser(UUID id, UserUpdateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();

        User user = userRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        if (!user.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("User not found in this tenant");
        }

        if (request.getUsername() != null && !request.getUsername().equals(user.getUsername())) {
            if (userRepository.existsByUsernameAndTenantId(request.getUsername(), tenantId)) {
                throw new DataIntegrityViolationException("Username already exists");
            }
            user.setUsername(request.getUsername());
        }

        if (request.getRoleIds() != null) {
            org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder
                    .getContext().getAuthentication();
            boolean isSuperAdmin = auth != null
                    && auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_SUPER_ADMIN"));

            Set<Role> roles = new HashSet<>();
            for (UUID roleId : request.getRoleIds()) {
                Role role = roleRepository.findById(roleId)
                        .orElseThrow(() -> new IllegalArgumentException("Role not found"));
                if (!role.getTenantId().equals(tenantId)) {
                    throw new IllegalArgumentException("Invalid role for this tenant");
                }
                if ("SUPER_ADMIN".equals(role.getName()) && !isSuperAdmin) {
                    throw new IllegalArgumentException("You do not have permission to assign the SUPER_ADMIN role");
                }
                roles.add(role);
            }
            user.setRoles(roles);
        }

        user = userRepository.save(user);
        return mapToDto(user);
    }

    @Transactional
    public void disableUser(UUID id) {
        String tenantId = TenantContext.getCurrentTenant();
        User user = userRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        if (!user.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("User not found in this tenant");
        }

        user.setStatus(UserStatus.INACTIVE);
        userRepository.save(user);
    }

    @Transactional
    public void enableUser(UUID id) {
        String tenantId = TenantContext.getCurrentTenant();
        User user = userRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        if (!user.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("User not found in this tenant");
        }

        user.setStatus(UserStatus.ACTIVE);
        userRepository.save(user);
    }

    @Transactional
    public void inviteUser(UserInviteRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        if (userRepository.existsByEmailAndTenantId(request.getEmail(), tenantId)) {
            throw new DataIntegrityViolationException("Email already exists");
        }
        if (userRepository.existsByUsernameAndTenantId(request.getUsername(), tenantId)) {
            throw new DataIntegrityViolationException("Username already exists");
        }

        User user = new User();
        user.setTenantId(tenantId);
        user.setUsername(request.getUsername());
        user.setEmail(request.getEmail());
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        user.setStatus(UserStatus.ACTIVE);

        if (request.getRoleIds() != null && !request.getRoleIds().isEmpty()) {
            org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder
                    .getContext().getAuthentication();
            boolean isSuperAdmin = auth != null
                    && auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_SUPER_ADMIN"));

            Set<Role> roles = new HashSet<>();
            for (UUID roleId : request.getRoleIds()) {
                Role role = roleRepository.findById(roleId)
                        .orElseThrow(() -> new IllegalArgumentException("Role not found"));
                if (!role.getTenantId().equals(tenantId)) {
                    throw new IllegalArgumentException("Invalid role for this tenant");
                }
                if ("SUPER_ADMIN".equals(role.getName()) && !isSuperAdmin) {
                    throw new IllegalArgumentException("You do not have permission to assign the SUPER_ADMIN role");
                }
                roles.add(role);
            }
            user.setRoles(roles);
        }

        userRepository.save(user);

        // Send email with credentials
        String loginLink = "http://localhost:5173/login";
        String message = "You have been invited to join the EAM System.\n\n" +
                "Here are your login credentials:\n" +
                "Username: " + request.getUsername() + "\n" +
                "Password: " + request.getPassword() + "\n\n" +
                "Please click the link below to login:\n" +
                loginLink + "\n\n" +
                "We recommend changing your password after your first login.";

        emailService.sendSimpleMessage(request.getEmail(), "EAM System - Invitation & Credentials", message);
    }

    private UserDto mapToDto(User user) {
        UserDto dto = new UserDto();
        dto.setId(user.getId());
        dto.setUsername(user.getUsername());
        dto.setEmail(user.getEmail());
        dto.setStatus(user.getStatus());
        dto.setCreatedAt(user.getCreatedAt());
        dto.setUpdatedAt(user.getUpdatedAt());

        if (user.getRoles() != null) {
            dto.setRoles(user.getRoles().stream()
                    .map(Role::getName)
                    .collect(Collectors.toSet()));
            dto.setRoleIds(user.getRoles().stream()
                    .map(Role::getId)
                    .collect(Collectors.toSet()));
        }
        return dto;
    }
}
