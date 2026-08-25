package com.eam.api.services;

import com.eam.api.models.dtos.MeterReadingDto;
import com.eam.api.models.entities.Asset;
import com.eam.api.models.entities.MeterReading;
import com.eam.api.repositories.AssetRepository;
import com.eam.api.repositories.MeterReadingRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class MeterReadingService {

    private final MeterReadingRepository meterReadingRepository;
    private final AssetRepository assetRepository;

    public MeterReadingService(MeterReadingRepository meterReadingRepository, AssetRepository assetRepository) {
        this.meterReadingRepository = meterReadingRepository;
        this.assetRepository = assetRepository;
    }

    @Transactional(readOnly = true)
    public List<MeterReadingDto> getMeterReadingsByAssetId(UUID assetId) {
        return meterReadingRepository.findByAssetIdOrderByReadingDateDesc(assetId).stream()
                .map(this::mapToDto)
                .collect(Collectors.toList());
    }

    @Transactional
    public MeterReadingDto createMeterReading(UUID assetId, MeterReadingDto dto) {
        Asset asset = assetRepository.findById(assetId)
                .orElseThrow(() -> new IllegalArgumentException("Asset not found"));

        MeterReading reading = new MeterReading();
        reading.setAsset(asset);
        reading.setReadingValue(dto.getReadingValue());
        reading.setReadingDate(dto.getReadingDate());
        reading.setUnit(dto.getUnit());
        reading.setRemarks(dto.getRemarks());

        reading = meterReadingRepository.save(reading);

        return mapToDto(reading);
    }

    private MeterReadingDto mapToDto(MeterReading entity) {
        MeterReadingDto dto = new MeterReadingDto();
        dto.setId(entity.getId());
        dto.setAssetId(entity.getAsset().getId());
        dto.setReadingValue(entity.getReadingValue());
        dto.setReadingDate(entity.getReadingDate());
        dto.setUnit(entity.getUnit());
        dto.setRemarks(entity.getRemarks());
        dto.setCreatedBy(entity.getCreatedBy());
        dto.setCreatedAt(entity.getCreatedAt());
        return dto;
    }
}
