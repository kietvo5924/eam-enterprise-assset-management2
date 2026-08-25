package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.TenantSettingsDto;
import com.eam.api.models.entities.Tenant;
import com.eam.api.repositories.TenantRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.DateTimeException;
import java.time.ZoneId;
import java.util.UUID;

@Service
public class TenantService {

    private final TenantRepository tenantRepository;

    public TenantService(TenantRepository tenantRepository) {
        this.tenantRepository = tenantRepository;
    }

    public TenantSettingsDto getTenantSettings() {
        String tenantId = TenantContext.getCurrentTenant();
        if (tenantId == null) {
            throw new RuntimeException("Tenant context is missing");
        }

        Tenant tenant = tenantRepository.findById(UUID.fromString(tenantId))
                .orElseThrow(() -> new RuntimeException("Tenant not found"));

        TenantSettingsDto dto = new TenantSettingsDto();
        dto.setName(tenant.getName());
        dto.setLogoUrl(tenant.getLogoUrl());
        dto.setTimezone(tenant.getTimezone());
        return dto;
    }

    @Transactional
    public TenantSettingsDto updateTenantSettings(TenantSettingsDto settingsDto) {
        String tenantId = TenantContext.getCurrentTenant();
        if (tenantId == null) {
            throw new RuntimeException("Tenant context is missing");
        }

        Tenant tenant = tenantRepository.findById(UUID.fromString(tenantId))
                .orElseThrow(() -> new RuntimeException("Tenant not found"));

        try {
            ZoneId.of(settingsDto.getTimezone());
        } catch (DateTimeException e) {
            throw new IllegalArgumentException("Invalid timezone: " + settingsDto.getTimezone());
        }

        tenant.setName(settingsDto.getName());
        tenant.setLogoUrl(settingsDto.getLogoUrl());
        tenant.setTimezone(settingsDto.getTimezone());

        Tenant savedTenant = tenantRepository.save(tenant);

        TenantSettingsDto dto = new TenantSettingsDto();
        dto.setName(savedTenant.getName());
        dto.setLogoUrl(savedTenant.getLogoUrl());
        dto.setTimezone(savedTenant.getTimezone());
        return dto;
    }
}
