package com.eam.api;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.entities.Permission;
import com.eam.api.models.entities.Role;
import com.eam.api.repositories.PermissionRepository;
import com.eam.api.repositories.RoleRepository;
import com.eam.api.repositories.UserRepository;
import com.eam.api.services.RoleService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class RoleServiceTest {

    @Mock
    private RoleRepository roleRepository;

    @Mock
    private PermissionRepository permissionRepository;

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private RoleService roleService;

    private final String TENANT_ID = UUID.randomUUID().toString();

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        TenantContext.setCurrentTenant(TENANT_ID);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void createRole_Success() {
        when(roleRepository.findByNameAndTenantId("Test Role", TENANT_ID)).thenReturn(Optional.empty());
        when(permissionRepository.findAllById(any())).thenReturn(List.of(new Permission("tenant:read", "Read Tenant", "")));
        
        Role savedRole = new Role();
        savedRole.setName("Test Role");
        savedRole.setTenantId(TENANT_ID);
        when(roleRepository.save(any(Role.class))).thenReturn(savedRole);

        Role role = roleService.createRole("Test Role", "Desc", List.of("tenant:read"));
        
        assertNotNull(role);
        assertEquals("Test Role", role.getName());
        assertEquals(TENANT_ID, role.getTenantId());
        verify(roleRepository).save(any(Role.class));
    }

    @Test
    void createRole_AlreadyExists_ThrowsException() {
        when(roleRepository.findByNameAndTenantId("Test Role", TENANT_ID)).thenReturn(Optional.of(new Role()));

        assertThrows(IllegalArgumentException.class, () -> {
            roleService.createRole("Test Role", "Desc", List.of("tenant:read"));
        });
    }

    @Test
    void deleteRole_SystemRole_ThrowsException() {
        Role sysRole = new Role();
        sysRole.setTenantId(TENANT_ID);
        sysRole.setIsSystem(true);
        UUID roleId = UUID.randomUUID();
        when(roleRepository.findById(roleId)).thenReturn(Optional.of(sysRole));

        assertThrows(IllegalArgumentException.class, () -> {
            roleService.deleteRole(roleId, null);
        });
    }
}
