package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.SparePartDto;
import com.eam.api.services.SparePartService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/spare-parts")
public class SparePartController {

    private final SparePartService sparePartService;

    public SparePartController(SparePartService sparePartService) {
        this.sparePartService = sparePartService;
    }

    @GetMapping
    @org.springframework.security.access.prepost.PreAuthorize("hasAuthority('inventory:read') or hasAuthority('system:admin')")
    public ResponseEntity<ApiResponse<List<SparePartDto>>> getAllSpareParts() {
        List<SparePartDto> parts = sparePartService.getAllSpareParts();
        return ResponseEntity.ok(ApiResponse.success(parts));
    }

    @PostMapping
    @org.springframework.security.access.prepost.PreAuthorize("hasAuthority('inventory:create') or hasAuthority('system:admin')")
    public ResponseEntity<ApiResponse<SparePartDto>> createSparePart(@RequestBody SparePartDto dto) {
        return ResponseEntity.ok(ApiResponse.success(sparePartService.createSparePart(dto)));
    }

    @PutMapping("/{id}")
    @org.springframework.security.access.prepost.PreAuthorize("hasAuthority('inventory:update') or hasAuthority('system:admin')")
    public ResponseEntity<ApiResponse<SparePartDto>> updateSparePart(@PathVariable String id, @RequestBody SparePartDto dto) {
        return ResponseEntity.ok(ApiResponse.success(sparePartService.updateSparePart(id, dto)));
    }

    @DeleteMapping("/{id}")
    @org.springframework.security.access.prepost.PreAuthorize("hasAuthority('inventory:delete') or hasAuthority('system:admin')")
    public ResponseEntity<ApiResponse<Void>> deleteSparePart(@PathVariable String id) {
        sparePartService.deleteSparePart(id);
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
