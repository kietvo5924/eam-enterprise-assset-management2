package com.eam.api.models.dtos;

import java.util.UUID;
import java.time.ZonedDateTime;

public record LocationDto(
    UUID id,
    String parentId,
    String name,
    String description,
    Boolean isActive,
    ZonedDateTime createdAt,
    ZonedDateTime updatedAt
) {}
