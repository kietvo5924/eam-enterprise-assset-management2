package com.eam.api.repositories;

import com.eam.api.models.entities.MeterReading;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface MeterReadingRepository extends JpaRepository<MeterReading, UUID> {
    List<MeterReading> findByAssetIdOrderByReadingDateDesc(UUID assetId);
    Optional<MeterReading> findFirstByAssetIdOrderByReadingDateDesc(UUID assetId);
}
