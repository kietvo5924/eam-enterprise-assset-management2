package com.eam.api.controllers;

import com.eam.api.models.dtos.MeterReadingDto;
import com.eam.api.services.MeterReadingService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/assets/{assetId}/meter-readings")
public class MeterReadingController {

    private final MeterReadingService meterReadingService;

    public MeterReadingController(MeterReadingService meterReadingService) {
        this.meterReadingService = meterReadingService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('ASSET_VIEW')")
    public ResponseEntity<List<MeterReadingDto>> getMeterReadings(@PathVariable UUID assetId) {
        return ResponseEntity.ok(meterReadingService.getMeterReadingsByAssetId(assetId));
    }

    @PostMapping
    @PreAuthorize("hasAuthority('ASSET_EDIT')")
    public ResponseEntity<MeterReadingDto> createMeterReading(
            @PathVariable UUID assetId,
            @RequestBody MeterReadingDto dto) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(meterReadingService.createMeterReading(assetId, dto));
    }
}
