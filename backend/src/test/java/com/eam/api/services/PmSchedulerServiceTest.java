package com.eam.api.services;

import com.eam.api.models.entities.Asset;
import com.eam.api.models.entities.PmPlan;
import com.eam.api.models.entities.PmPlanAssignment;
import com.eam.api.models.enums.PmTriggerType;
import com.eam.api.models.enums.PmIntervalUnit;
import com.eam.api.models.events.MaintenanceTriggeredEvent;
import com.eam.api.repositories.PmPlanAssignmentRepository;
import com.eam.api.repositories.WorkOrderRepository;
import com.eam.api.models.entities.WorkOrder;
import com.eam.api.models.enums.WorkOrderStatus;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.messaging.Message;

import java.math.BigDecimal;
import java.time.ZonedDateTime;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class PmSchedulerServiceTest {

    @Mock
    private PmPlanAssignmentRepository assignmentRepository;

    @Mock
    private WorkOrderRepository workOrderRepository;

    @Mock
    private KafkaTemplate<String, Object> kafkaTemplate;

    @InjectMocks
    private PmSchedulerService pmSchedulerService;

    @Test
    void testEvaluateTriggers_TimeBased_ShouldTrigger() throws Exception {
        // Arrange
        Asset asset = new Asset();
        asset.setId(UUID.randomUUID());
        asset.setName("Test Asset");

        PmPlan plan = new PmPlan();
        plan.setId(UUID.randomUUID());
        plan.setName("Test Plan");
        plan.setTriggerType(PmTriggerType.TIME);
        plan.setIntervalValue(new BigDecimal("1"));
        plan.setIntervalUnit(PmIntervalUnit.DAYS);
        plan.setSuppressIfPending(false); // To ensure it triggers in default case
        plan.setIsFloatingSchedule(false);

        PmPlanAssignment assignment = new PmPlanAssignment();
        assignment.setTenantId("tenant1");
        assignment.setAsset(asset);
        assignment.setPmPlan(plan);
        // Created 2 days ago, so it should trigger
        assignment.setCreatedAt(ZonedDateTime.now().minusDays(2));

        when(assignmentRepository.findAllActiveAssignments()).thenReturn(Collections.singletonList(assignment));
        when(kafkaTemplate.send(any(Message.class))).thenReturn(CompletableFuture.completedFuture(null));

        // Act
        pmSchedulerService.evaluateTriggers();

        // Assert
        ArgumentCaptor<PmPlanAssignment> assignmentCaptor = ArgumentCaptor.forClass(PmPlanAssignment.class);
        verify(assignmentRepository, times(1)).save(assignmentCaptor.capture());
        
        PmPlanAssignment savedAssignment = assignmentCaptor.getValue();
        assertNotNull(savedAssignment.getLastTriggeredAt());

        ArgumentCaptor<Message<MaintenanceTriggeredEvent>> messageCaptor = ArgumentCaptor.forClass(Message.class);
        verify(kafkaTemplate, times(1)).send(messageCaptor.capture());

        Message<MaintenanceTriggeredEvent> msg = messageCaptor.getValue();
        assertNotNull(msg.getPayload());
        assertEquals(plan.getId(), msg.getPayload().getPmPlanId());
    }

    @Test
    void testEvaluateTriggers_TimeBased_NotDue() throws Exception {
        // Arrange
        Asset asset = new Asset();
        asset.setId(UUID.randomUUID());

        PmPlan plan = new PmPlan();
        plan.setId(UUID.randomUUID());
        plan.setTriggerType(PmTriggerType.TIME);
        plan.setIntervalValue(new BigDecimal("1"));
        plan.setIntervalUnit(PmIntervalUnit.DAYS);

        PmPlanAssignment assignment = new PmPlanAssignment();
        assignment.setAsset(asset);
        assignment.setPmPlan(plan);
        // Created just now, so it's due in 1 day
        assignment.setCreatedAt(ZonedDateTime.now());

        when(assignmentRepository.findAllActiveAssignments()).thenReturn(Collections.singletonList(assignment));

        // Act
        pmSchedulerService.evaluateTriggers();

        // Assert
        verify(assignmentRepository, never()).save(any());
        verify(kafkaTemplate, never()).send(any(Message.class));
    }

    @Test
    void testEvaluateTriggers_TimeBased_SuppressIfPending() throws Exception {
        // Arrange
        Asset asset = new Asset();
        asset.setId(UUID.randomUUID());

        PmPlan plan = new PmPlan();
        plan.setId(UUID.randomUUID());
        plan.setTriggerType(PmTriggerType.TIME);
        plan.setIntervalValue(new BigDecimal("1"));
        plan.setIntervalUnit(PmIntervalUnit.DAYS);
        plan.setSuppressIfPending(true); // Feature enabled

        PmPlanAssignment assignment = new PmPlanAssignment();
        assignment.setAsset(asset);
        assignment.setPmPlan(plan);
        // Created 2 days ago, so it should trigger IF NOT SUPPRESSED
        assignment.setCreatedAt(ZonedDateTime.now().minusDays(2));

        when(assignmentRepository.findAllActiveAssignments()).thenReturn(Collections.singletonList(assignment));
        // Mock that a pending WO exists
        when(workOrderRepository.existsBySourceReferenceAndStatusNotIn(anyString(), anyList())).thenReturn(true);

        // Act
        pmSchedulerService.evaluateTriggers();

        // Assert
        verify(assignmentRepository, never()).save(any());
        verify(kafkaTemplate, never()).send(any(Message.class));
    }

    @Test
    void testEvaluateTriggers_TimeBased_FloatingSchedule() throws Exception {
        // Arrange
        Asset asset = new Asset();
        asset.setId(UUID.randomUUID());

        PmPlan plan = new PmPlan();
        plan.setId(UUID.randomUUID());
        plan.setTriggerType(PmTriggerType.TIME);
        plan.setIntervalValue(new BigDecimal("1"));
        plan.setIntervalUnit(PmIntervalUnit.DAYS);
        plan.setSuppressIfPending(false);
        plan.setIsFloatingSchedule(true); // Feature enabled

        PmPlanAssignment assignment = new PmPlanAssignment();
        assignment.setTenantId("tenant1");
        assignment.setAsset(asset);
        assignment.setPmPlan(plan);
        // Created 10 days ago, last triggered 5 days ago
        assignment.setCreatedAt(ZonedDateTime.now().minusDays(10));
        assignment.setLastTriggeredAt(ZonedDateTime.now().minusDays(5));

        // Mock a completed WO from 2 days ago
        WorkOrder completedWo = new WorkOrder();
        completedWo.setCompletedAt(ZonedDateTime.now().minusDays(2));

        when(assignmentRepository.findAllActiveAssignments()).thenReturn(Collections.singletonList(assignment));
        when(workOrderRepository.findFirstBySourceReferenceAndStatusOrderByCompletedAtDesc(anyString(), eq(WorkOrderStatus.COMPLETED)))
                .thenReturn(java.util.Optional.of(completedWo));
        when(kafkaTemplate.send(any(Message.class))).thenReturn(CompletableFuture.completedFuture(null));

        // Act
        pmSchedulerService.evaluateTriggers();

        // Assert
        ArgumentCaptor<PmPlanAssignment> assignmentCaptor = ArgumentCaptor.forClass(PmPlanAssignment.class);
        verify(assignmentRepository, times(1)).save(assignmentCaptor.capture());
        
        PmPlanAssignment savedAssignment = assignmentCaptor.getValue();
        // Since interval is 1 day and completed was 2 days ago, new due date is completed + 1 day = 1 day ago
        // So it triggers, and next due date should be (completedAt + 1 day).
        assertNotNull(savedAssignment.getLastTriggeredAt());
        assertTrue(savedAssignment.getLastTriggeredAt().isBefore(ZonedDateTime.now()));
    }
}
