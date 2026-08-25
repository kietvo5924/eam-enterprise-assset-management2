package com.eam.api.models.dtos;

import java.time.LocalDate;
import java.time.ZonedDateTime;
import java.math.BigDecimal;
import java.util.UUID;
import com.eam.api.models.enums.AssetStatus;

public record AssetResponse(
    UUID id,
    String name,
    UUID categoryId,
    String categoryName,
    String parentId,
    String serialNumber,
    String model,
    String manufacturer,
    LocalDate purchaseDate,
    BigDecimal value,
    AssetStatus status,
    UUID locationId,
    String locationName,
    UUID hierarchyTemplateId,
    String hierarchyTemplateName,
    String qrCode,
    Boolean isActive,
    ZonedDateTime createdAt,
    ZonedDateTime updatedAt,
    String createdByName,
    String updatedByName
) {}
