package com.eam.api.repositories;

import com.eam.api.models.entities.Role;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface RoleRepository extends JpaRepository<Role, UUID> {
    List<Role> findByTenantId(String tenantId);
    Optional<Role> findByNameAndTenantId(String name, String tenantId);
}
