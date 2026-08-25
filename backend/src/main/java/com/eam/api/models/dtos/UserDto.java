package com.eam.api.models.dtos;

import com.eam.api.models.entities.UserStatus;
import java.time.ZonedDateTime;
import java.util.Set;
import java.util.UUID;

public class UserDto {
    private UUID id;
    private String username;
    private String email;
    private UserStatus status;
    private ZonedDateTime createdAt;
    private ZonedDateTime updatedAt;
    private Set<String> roles;
    private Set<UUID> roleIds;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public UserStatus getStatus() { return status; }
    public void setStatus(UserStatus status) { this.status = status; }

    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }

    public ZonedDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(ZonedDateTime updatedAt) { this.updatedAt = updatedAt; }

    public Set<String> getRoles() { return roles; }
    public void setRoles(Set<String> roles) { this.roles = roles; }

    public Set<UUID> getRoleIds() { return roleIds; }
    public void setRoleIds(Set<UUID> roleIds) { this.roleIds = roleIds; }
}
