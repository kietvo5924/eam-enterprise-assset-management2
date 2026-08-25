package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.PmPlanCreateRequest;
import com.eam.api.models.dtos.PmPlanDto;
import com.eam.api.models.entities.PmPlan;
import com.eam.api.models.enums.PmIntervalUnit;
import com.eam.api.models.enums.PmTriggerType;
import com.eam.api.models.entities.Asset;
import com.eam.api.models.dtos.AssignPmPlanRequest;
import com.eam.api.repositories.PmPlanRepository;
import com.eam.api.repositories.AssetRepository;
import com.eam.api.repositories.PmPlanAssignmentRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Set;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class PmPlanServiceTest {

    @Mock
    private PmPlanRepository pmPlanRepository;

    @Mock
    private AssetRepository assetRepository;

    @Mock
    private PmPlanAssignmentRepository pmPlanAssignmentRepository;

    @InjectMocks
    private PmPlanService pmPlanService;

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
    void createPmPlan_ShouldReturnDto_WhenSuccessful() {
        PmPlanCreateRequest request = new PmPlanCreateRequest();
        request.setName("Monthly HVAC Maintenance");
        request.setTriggerType(PmTriggerType.TIME);
        request.setIntervalValue(BigDecimal.valueOf(30));
        request.setIntervalUnit(PmIntervalUnit.DAYS);

        when(pmPlanRepository.save(any(PmPlan.class))).thenAnswer(i -> {
            PmPlan p = i.getArgument(0);
            p.setId(UUID.randomUUID());
            return p;
        });

        PmPlanDto response = pmPlanService.createPmPlan(request);

        assertNotNull(response);
        assertEquals("Monthly HVAC Maintenance", response.getName());
        assertEquals(PmTriggerType.TIME, response.getTriggerType());
        verify(pmPlanRepository, times(1)).save(any(PmPlan.class));
    }

    @Test
    void deletePmPlan_ShouldDelete_WhenExists() {
        UUID id = UUID.randomUUID();
        PmPlan plan = new PmPlan();
        plan.setId(id);

        when(pmPlanRepository.findById(id)).thenReturn(Optional.of(plan));

        pmPlanService.deletePmPlan(id);

        verify(pmPlanRepository, times(1)).delete(plan);
    }

    @Test
    void assignPmPlanToAssets_ShouldSaveAssignment_WhenValid() {
        UUID planId = UUID.randomUUID();
        UUID assetId = UUID.randomUUID();

        PmPlan plan = new PmPlan();
        plan.setId(planId);
        plan.setTenantId(TENANT_ID);

        Asset asset = new Asset();
        asset.setId(assetId);
        asset.setTenantId(TENANT_ID);

        AssignPmPlanRequest request = new AssignPmPlanRequest();
        request.setAssetIds(Set.of(assetId));

        when(pmPlanRepository.findById(planId)).thenReturn(Optional.of(plan));
        when(assetRepository.findAllById(Set.of(assetId))).thenReturn(List.of(asset));
        when(pmPlanAssignmentRepository.findByPmPlanId(planId)).thenReturn(List.of());

        pmPlanService.assignPmPlanToAssets(planId, request);

        verify(pmPlanAssignmentRepository, times(1)).saveAll(anyList());
    }

    @Test
    void assignPmPlanToAssets_ShouldThrowException_WhenCrossTenant() {
        UUID planId = UUID.randomUUID();
        UUID assetId = UUID.randomUUID();

        PmPlan plan = new PmPlan();
        plan.setId(planId);
        plan.setTenantId(TENANT_ID);

        Asset asset = new Asset();
        asset.setId(assetId);
        asset.setTenantId("00000000-0000-0000-0000-000000000002"); // Different tenant

        AssignPmPlanRequest request = new AssignPmPlanRequest();
        request.setAssetIds(Set.of(assetId));

        when(pmPlanRepository.findById(planId)).thenReturn(Optional.of(plan));
        when(assetRepository.findAllById(Set.of(assetId))).thenReturn(List.of(asset));

        Exception exception = assertThrows(IllegalArgumentException.class, () -> {
            pmPlanService.assignPmPlanToAssets(planId, request);
        });

        assertEquals("Asset " + assetId + " does not belong to the same tenant as PM Plan.", exception.getMessage());
        verify(pmPlanAssignmentRepository, never()).saveAll(anyList());
    }
}
