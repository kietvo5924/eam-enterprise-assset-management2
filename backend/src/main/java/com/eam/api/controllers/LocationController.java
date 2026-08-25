package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.LocationCreateRequest;
import com.eam.api.models.dtos.LocationDto;
import com.eam.api.models.dtos.LocationUpdateRequest;
import com.eam.api.services.LocationService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import jakarta.validation.constraints.Min;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/locations")
public class LocationController {

    private final LocationService locationService;

    public LocationController(LocationService locationService) {
        this.locationService = locationService;
    }

    @GetMapping
    @PreAuthorize("hasAnyAuthority('location:read', 'asset:read')")
    public ApiResponse<Page<LocationDto>> getLocations(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) int size) {
        return ApiResponse.success(locationService.getLocations(PageRequest.of(page, size)));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAnyAuthority('location:read', 'asset:read')")
    public ApiResponse<LocationDto> getLocation(@PathVariable UUID id) {
        return ApiResponse.success(locationService.getLocationById(id));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAuthority('location:create')")
    public ApiResponse<LocationDto> createLocation(@Valid @RequestBody LocationCreateRequest request) {
        return ApiResponse.success(locationService.createLocation(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAuthority('location:update')")
    public ApiResponse<LocationDto> updateLocation(
            @PathVariable UUID id, 
            @Valid @RequestBody LocationUpdateRequest request) {
        return ApiResponse.success(locationService.updateLocation(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('location:delete')")
    public ApiResponse<Void> deleteLocation(@PathVariable UUID id) {
        locationService.deleteLocation(id);
        return ApiResponse.success(null);
    }
}
