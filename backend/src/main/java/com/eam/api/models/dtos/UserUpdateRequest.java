package com.eam.api.models.dtos;

import java.util.Set;
import java.util.UUID;

public class UserUpdateRequest {
    private String username;
    private Set<UUID> roleIds;

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public Set<UUID> getRoleIds() { return roleIds; }
    public void setRoleIds(Set<UUID> roleIds) { this.roleIds = roleIds; }
}
