package com.eam.api.services;

import com.eam.api.models.entities.Asset;
import com.eam.api.models.entities.WorkOrder;
import com.eam.api.models.enums.PmTriggerType;
import com.eam.api.models.enums.WorkOrderStatus;
import com.eam.api.models.events.MaintenanceTriggeredEvent;
import com.eam.api.repositories.AssetRepository;
import com.eam.api.repositories.WorkOrderRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;

import java.util.Arrays;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class WorkOrderKafkaConsumerTest {

    @Mock
    private WorkOrderRepository workOrderRepository;

    @Mock
    private AssetRepository assetRepository;

    @Mock
    private KafkaTemplate<String, Object> kafkaTemplate;

    @InjectMocks
    private WorkOrderKafkaConsumer consumer;

    @Test
    void testHandleEvent_Success() {
        // Arrange
        UUID assetId = UUID.randomUUID();
        UUID planId = UUID.randomUUID();
        
        MaintenanceTriggeredEvent event = new MaintenanceTriggeredEvent(
                "tenant1", assetId, planId, PmTriggerType.TIME, "MEDIUM", "Test Title", "Test Desc", java.time.ZonedDateTime.now()
        );

        String sourceRef = "PM_" + planId + "_ASSET_" + assetId;
        when(workOrderRepository.existsBySourceReferenceAndStatusNotIn(
                eq(sourceRef), eq(Arrays.asList(WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELED)))
        ).thenReturn(false);

        Asset asset = new Asset();
        asset.setId(assetId);
        when(assetRepository.findById(assetId)).thenReturn(Optional.of(asset));

        // Act
        consumer.handleMaintenanceTriggeredEvent(event);

        // Assert
        ArgumentCaptor<WorkOrder> woCaptor = ArgumentCaptor.forClass(WorkOrder.class);
        verify(workOrderRepository).save(woCaptor.capture());
        
        WorkOrder savedWo = woCaptor.getValue();
        assertEquals("Test Title", savedWo.getTitle());
        assertEquals(sourceRef, savedWo.getSourceReference());
        assertEquals(WorkOrderStatus.CREATED, savedWo.getStatus());
        
        verify(kafkaTemplate).send(eq("workorder.events"), any());
    }

    @Test
    void testHandleEvent_IdempotencyBlock() {
        // Arrange
        UUID assetId = UUID.randomUUID();
        UUID planId = UUID.randomUUID();
        
        MaintenanceTriggeredEvent event = new MaintenanceTriggeredEvent(
                "tenant1", assetId, planId, PmTriggerType.TIME, "MEDIUM", "Test Title", "Test Desc", java.time.ZonedDateTime.now()
        );

        String sourceRef = "PM_" + planId + "_ASSET_" + assetId;
        when(workOrderRepository.existsBySourceReferenceAndStatusNotIn(
                eq(sourceRef), eq(Arrays.asList(WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELED)))
        ).thenReturn(true); // Already exists!

        // Act
        consumer.handleMaintenanceTriggeredEvent(event);

        // Assert
        verify(assetRepository, never()).findById(any());
        verify(workOrderRepository, never()).save(any());
        verify(kafkaTemplate, never()).send(anyString(), any());
    }
}
