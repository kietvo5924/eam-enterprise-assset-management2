package com.eam.api.repositories;

import com.eam.api.models.entities.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;
import java.util.List;

@Repository
public interface UserRepository extends JpaRepository<User, UUID> {
    Optional<User> findByUsernameAndTenantId(String username, String tenantId);
    Optional<User> findByEmailAndTenantId(String email, String tenantId);
    Optional<User> findByResetToken(String resetToken);
    @Query("SELECT u FROM User u WHERE u.email = :email")
    List<User> findAllByEmail(@org.springframework.data.repository.query.Param("email") String email);
    boolean existsByEmailAndTenantId(String email, String tenantId);
    boolean existsByUsernameAndTenantId(String username, String tenantId);
    List<User> findByUsernameContainingIgnoreCase(String username);
    @Query("SELECT u FROM User u LEFT JOIN FETCH u.roles WHERE u.tenantId = :tenantId")
    List<User> findByTenantId(String tenantId);
    org.springframework.data.domain.Page<User> findByTenantId(String tenantId, org.springframework.data.domain.Pageable pageable);
    
    org.springframework.data.domain.Page<User> findByRolesNameAndTenantId(String roleName, String tenantId, org.springframework.data.domain.Pageable pageable);
    
    org.springframework.data.domain.Page<User> findByRolesPermissionsIdAndTenantId(String permissionId, String tenantId, org.springframework.data.domain.Pageable pageable);
    
    List<User> findByRolesIdAndTenantId(UUID roleId, String tenantId);
    
    @Query("SELECT u FROM User u WHERE u.id != :superAdminId")
    org.springframework.data.domain.Page<User> findAllExcludingSuperAdmin(@org.springframework.data.repository.query.Param("superAdminId") java.util.UUID superAdminId, org.springframework.data.domain.Pageable pageable);

    @Query("SELECT DISTINCT u FROM User u JOIN u.roles r WHERE r.name = :roleName AND u.id != :superAdminId")
    org.springframework.data.domain.Page<User> findByRolesNameExcludingSuperAdmin(@org.springframework.data.repository.query.Param("roleName") String roleName, @org.springframework.data.repository.query.Param("superAdminId") java.util.UUID superAdminId, org.springframework.data.domain.Pageable pageable);

    @Query("SELECT DISTINCT u FROM User u JOIN u.roles r JOIN r.permissions p WHERE p.id = :permissionId AND u.id != :superAdminId")
    org.springframework.data.domain.Page<User> findByRolesPermissionsIdExcludingSuperAdmin(@org.springframework.data.repository.query.Param("permissionId") String permissionId, @org.springframework.data.repository.query.Param("superAdminId") java.util.UUID superAdminId, org.springframework.data.domain.Pageable pageable);
}
