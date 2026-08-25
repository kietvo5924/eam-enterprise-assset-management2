package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.util.Set;
import java.util.UUID;

public class AssignPmPlanRequest {

    @NotEmpty(message = "Asset IDs list cannot be empty")
    private Set<@NotNull UUID> assetIds;

    public Set<UUID> getAssetIds() {
        return assetIds;
    }

    public void setAssetIds(Set<UUID> assetIds) {
        this.assetIds = assetIds;
    }
}
