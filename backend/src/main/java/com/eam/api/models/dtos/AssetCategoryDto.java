package com.eam.api.models.dtos;

import java.util.UUID;
import java.time.ZonedDateTime;

public record AssetCategoryDto(
        UUID id,
        String tenantId,
        String name,
        String description,
        Boolean isActive,
        ZonedDateTime createdAt,
        ZonedDateTime updatedAt) {
}
