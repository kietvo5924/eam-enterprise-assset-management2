package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;
import java.math.BigDecimal;
import java.util.UUID;
import com.eam.api.models.enums.AssetStatus;

public record AssetUpdateRequest(
    @NotBlank(message = "Tên tài sản không được bỏ trống")
    @Size(max = 255, message = "Tên tài sản không được vượt quá 255 ký tự")
    String name,

    UUID categoryId,
    
    @Size(max = 100, message = "Serial number không được vượt quá 100 ký tự")
    String serialNumber,
    
    @Size(max = 100, message = "Model không được vượt quá 100 ký tự")
    String model,
    
    @Size(max = 100, message = "Nhà sản xuất không được vượt quá 100 ký tự")
    String manufacturer,
    
    LocalDate purchaseDate,
    
    BigDecimal value,
    
    AssetStatus status,
    
    UUID locationId,
    
    UUID hierarchyTemplateId,
    
    Boolean isActive
) {}
