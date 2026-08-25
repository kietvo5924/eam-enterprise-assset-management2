package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.SparePartDto;
import com.eam.api.models.entities.SparePart;
import com.eam.api.repositories.SparePartRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class SparePartService {

    private final SparePartRepository sparePartRepository;

    public SparePartService(SparePartRepository sparePartRepository) {
        this.sparePartRepository = sparePartRepository;
    }

    @Transactional(readOnly = true)
    public List<SparePartDto> getAllSpareParts() {
        String tenantId = TenantContext.getCurrentTenant();
        return sparePartRepository.findByTenantId(tenantId, org.springframework.data.domain.Pageable.unpaged())
                .stream()
                .map(this::mapToDto)
                .collect(Collectors.toList());
    }

    @Transactional
    public SparePartDto createSparePart(SparePartDto dto) {
        String tenantId = TenantContext.getCurrentTenant();
        SparePart sp = new SparePart();
        sp.setTenantId(tenantId);
        sp.setName(dto.getName());
        sp.setPartNumber(dto.getPartNumber());
        sp.setDescription(dto.getDescription());
        sp.setQuantityInStock(dto.getQuantityInStock() != null ? dto.getQuantityInStock() : java.math.BigDecimal.ZERO);
        sp.setUnitCost(dto.getUnitCost());
        sparePartRepository.save(sp);
        return mapToDto(sp);
    }

    @Transactional
    public SparePartDto updateSparePart(String id, SparePartDto dto) {
        SparePart sp = sparePartRepository.findById(java.util.UUID.fromString(id))
                .orElseThrow(() -> new RuntimeException("Spare Part not found"));
        sp.setName(dto.getName());
        sp.setPartNumber(dto.getPartNumber());
        sp.setDescription(dto.getDescription());
        if (dto.getQuantityInStock() != null) sp.setQuantityInStock(dto.getQuantityInStock());
        sp.setUnitCost(dto.getUnitCost());
        sparePartRepository.save(sp);
        return mapToDto(sp);
    }

    @Transactional
    public void deleteSparePart(String id) {
        sparePartRepository.deleteById(java.util.UUID.fromString(id));
    }

    private SparePartDto mapToDto(SparePart sp) {
        SparePartDto dto = new SparePartDto();
        dto.setId(sp.getId());
        dto.setName(sp.getName());
        dto.setPartNumber(sp.getPartNumber());
        dto.setDescription(sp.getDescription());
        dto.setQuantityInStock(sp.getQuantityInStock());
        dto.setUnitCost(sp.getUnitCost());
        dto.setCreatedAt(sp.getCreatedAt());
        dto.setUpdatedAt(sp.getUpdatedAt());
        return dto;
    }
}
