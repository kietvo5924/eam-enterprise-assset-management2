package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.LocationCreateRequest;
import com.eam.api.models.dtos.LocationDto;
import com.eam.api.models.dtos.LocationUpdateRequest;
import com.eam.api.models.entities.Location;
import com.eam.api.repositories.LocationRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
public class LocationService {

    private final LocationRepository locationRepository;

    public LocationService(LocationRepository locationRepository) {
        this.locationRepository = locationRepository;
    }

    @Transactional(readOnly = true)
    public Page<LocationDto> getLocations(Pageable pageable) {
        String tenantId = TenantContext.getCurrentTenant();
        return locationRepository.findByTenantId(tenantId, pageable)
                .map(this::mapToDto);
    }

    @Transactional(readOnly = true)
    public LocationDto getLocationById(UUID id) {
        return mapToDto(findByIdAndTenantId(id));
    }

    @Transactional
    public LocationDto createLocation(LocationCreateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        
        Location location = new Location();
        location.setTenantId(tenantId);
        location.setName(request.name());
        
        String parentId = request.parentId();
        if (parentId != null && parentId.trim().isEmpty()) {
            parentId = null;
        } else if (parentId != null) {
            parentId = formatToLtree(parentId);
        }
        location.setParentId(parentId);
        location.setDescription(request.description());
        location.setIsActive(request.isActive() != null ? request.isActive() : true);
        
        return mapToDto(locationRepository.save(location));
    }

    @Transactional
    public LocationDto updateLocation(UUID id, LocationUpdateRequest request) {
        Location location = findByIdAndTenantId(id);
        
        location.setName(request.name());
        
        String parentId = request.parentId();
        if (parentId != null && parentId.trim().isEmpty()) {
            parentId = null;
        } else if (parentId != null) {
            parentId = formatToLtree(parentId);
        }
        location.setParentId(parentId);
        
        location.setDescription(request.description());
        if (request.isActive() != null) location.setIsActive(request.isActive());

        return mapToDto(locationRepository.save(location));
    }

    @Transactional
    public void deleteLocation(UUID id) {
        Location location = findByIdAndTenantId(id);
        location.setIsActive(false);
        locationRepository.save(location);
    }

    private Location findByIdAndTenantId(UUID id) {
        String tenantId = TenantContext.getCurrentTenant();
        return locationRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Location not found"));
    }

    private String formatToLtree(String input) {
        if (input == null) return null;
        // Postgres ltree accepts alphanumeric and underscores, separated by dots.
        // We will strip Vietnamese diacritics and replace spaces/invalid chars with underscores
        String normalized = java.text.Normalizer.normalize(input, java.text.Normalizer.Form.NFD);
        String noDiacritics = normalized.replaceAll("\\p{InCombiningDiacriticalMarks}+", "");
        // Replace any non-alphanumeric (except dots) with underscore
        String ltree = noDiacritics.replaceAll("[^a-zA-Z0-9\\.]", "_");
        // Remove consecutive underscores and dots
        ltree = ltree.replaceAll("_+", "_").replaceAll("\\.+", ".");
        // Strip trailing/leading dots or underscores
        ltree = ltree.replaceAll("^[\\._]+|[\\._]+$", "");
        return ltree;
    }

    private LocationDto mapToDto(Location location) {
        return new LocationDto(
                location.getId(),
                location.getParentId(),
                location.getName(),
                location.getDescription(),
                location.getIsActive(),
                location.getCreatedAt(),
                location.getUpdatedAt()
        );
    }
}
