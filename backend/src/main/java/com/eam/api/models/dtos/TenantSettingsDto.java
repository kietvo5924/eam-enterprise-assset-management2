package com.eam.api.models.dtos;

import jakarta.validation.constraints.NotBlank;

public class TenantSettingsDto {

    @NotBlank(message = "Name is required")
    private String name;
    
    private String logoUrl;
    
    @NotBlank(message = "Timezone is required")
    private String timezone;

    // Getters and Setters

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getLogoUrl() {
        return logoUrl;
    }

    public void setLogoUrl(String logoUrl) {
        this.logoUrl = logoUrl;
    }

    public String getTimezone() {
        return timezone;
    }

    public void setTimezone(String timezone) {
        this.timezone = timezone;
    }
}
