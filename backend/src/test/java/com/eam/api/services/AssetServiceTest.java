package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.AssetCreateRequest;
import com.eam.api.models.dtos.AssetResponse;
import com.eam.api.models.entities.Asset;
import com.eam.api.repositories.AssetCategoryRepository;
import com.eam.api.repositories.AssetRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class AssetServiceTest {

    @Mock
    private AssetRepository assetRepository;

    @Mock
    private AssetCategoryRepository categoryRepository;

    @Mock
    private com.eam.api.repositories.LocationRepository locationRepository;

    @InjectMocks
    private AssetService assetService;

    private final String TENANT_ID = "00000000-0000-0000-0000-000000000001";

    @BeforeEach
    void setUp() {
        TenantContext.setCurrentTenant(TENANT_ID);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void createAsset_ShouldGenerateUniqueQrCode_WhenSuccessful() {
        AssetCreateRequest request = new AssetCreateRequest(
                "Test Asset", null, "SN123", "M1", "Man1", null, null, com.eam.api.models.enums.AssetStatus.OPERATIONAL,
                null, null, true);

        when(assetRepository.existsByQrCodeAndTenantId(anyString(), eq(TENANT_ID))).thenReturn(false);
        when(assetRepository.save(any(Asset.class))).thenAnswer(i -> {
            Asset a = i.getArgument(0);
            a.setId(UUID.randomUUID());
            return a;
        });

        AssetResponse response = assetService.createAsset(request);

        assertNotNull(response);
        assertEquals("Test Asset", response.name());
        assertNotNull(response.qrCode());
        assertTrue(response.qrCode().startsWith("AST-"));

        verify(assetRepository, times(1)).save(any(Asset.class));
    }

    @Test
    void deleteAsset_ShouldSetIsActiveToFalse_WhenAssetExists() {
        UUID id = UUID.randomUUID();
        Asset asset = new Asset();
        asset.setId(id);
        asset.setTenantId(TENANT_ID);
        asset.setIsActive(true);

        when(assetRepository.findByIdAndTenantIdAndIsActiveTrue(id, TENANT_ID)).thenReturn(Optional.of(asset));
        when(assetRepository.save(any(Asset.class))).thenReturn(asset);

        assetService.deleteAsset(id);

        assertFalse(asset.getIsActive());
        verify(assetRepository, times(1)).save(asset);
    }
}
