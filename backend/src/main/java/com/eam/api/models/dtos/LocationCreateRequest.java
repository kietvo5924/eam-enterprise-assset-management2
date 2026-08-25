package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record LocationCreateRequest(
    String parentId,
    
    @NotBlank(message = "Tên vị trí không được bỏ trống")
    @Size(max = 255, message = "Tên vị trí không được vượt quá 255 ký tự")
    String name,
    
    String description,
    
    Boolean isActive
) {}
