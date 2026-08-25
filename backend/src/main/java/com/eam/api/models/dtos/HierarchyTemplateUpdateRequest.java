package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record HierarchyTemplateUpdateRequest(
    @NotBlank(message = "Tên template không được bỏ trống")
    @Size(max = 255, message = "Tên template không được vượt quá 255 ký tự")
    String name,
    
    @Pattern(regexp = "^[a-zA-Z0-9_]+(\\.[a-zA-Z0-9_]+)*$", message = "Định dạng path không hợp lệ (ltree)")
    String path,
    
    String description,
    
    Boolean isActive
) {}
