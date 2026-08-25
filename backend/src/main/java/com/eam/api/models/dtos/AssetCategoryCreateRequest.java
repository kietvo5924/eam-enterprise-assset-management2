package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record AssetCategoryCreateRequest(
    @NotBlank(message = "Tên category không được bỏ trống")
    @Size(max = 255, message = "Tên category không được vượt quá 255 ký tự")
    String name,
    
    String description,
    
    Boolean isActive
) {}
