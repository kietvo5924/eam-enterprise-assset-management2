package com.eam.api.models.dtos;

import java.util.List;

public record AssetImportResultDto(
    int successCount,
    int failureCount,
    List<String> errors
) {}
