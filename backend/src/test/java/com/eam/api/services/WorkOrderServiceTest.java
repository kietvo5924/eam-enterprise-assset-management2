package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.WorkOrderDto;
import com.eam.api.models.dtos.WorkOrderStatusUpdateRequest;
import com.eam.api.models.entities.WorkOrder;
import com.eam.api.models.enums.WorkOrderStatus;
import com.eam.api.repositories.AssetRepository;
import com.eam.api.repositories.UserRepository;
import com.eam.api.repositories.WorkOrderRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import com.eam.api.core.security.CustomUserDetails;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.util.Collections;
import java.util.Optional;
import java.util.UUID;
import java.time.ZonedDateTime;
import java.time.ZoneOffset;
import java.util.Arrays;
import java.util.List;
import com.eam.api.models.dtos.MaintenanceCalendarEventDto;
import com.eam.api.repositories.PmPlanAssignmentRepository;
import com.eam.api.models.entities.PmPlanAssignment;
import com.eam.api.models.entities.PmPlan;
import com.eam.api.models.enums.PmTriggerType;
import com.eam.api.models.enums.PmIntervalUnit;
import com.eam.api.models.entities.Asset;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class WorkOrderServiceTest {

    @Mock
    private WorkOrderRepository workOrderRepository;

    @Mock
    private AssetRepository assetRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private PmPlanAssignmentRepository pmPlanAssignmentRepository;

    @Mock
    private KafkaTemplate<String, Object> kafkaTemplate;

    @Mock
    private ObjectMapper objectMapper;

    @Mock
    private org.springframework.context.ApplicationContext context;

    @Mock
    private com.eam.api.services.AuditLogService auditLogService;

    @InjectMocks
    private WorkOrderService workOrderService;

    private final String TENANT_ID = "00000000-0000-0000-0000-000000000001";
    private final UUID USER_ID = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        org.springframework.test.util.ReflectionTestUtils.setField(workOrderService, "context", context);
        
        com.eam.api.repositories.WorkOrderChecklistRepository checklistRepo = mock(com.eam.api.repositories.WorkOrderChecklistRepository.class);
        lenient().when(context.getBean(com.eam.api.repositories.WorkOrderChecklistRepository.class)).thenReturn(checklistRepo);
        
        com.eam.api.repositories.WorkOrderAttachmentRepository attachmentRepo = mock(com.eam.api.repositories.WorkOrderAttachmentRepository.class);
        lenient().when(context.getBean(com.eam.api.repositories.WorkOrderAttachmentRepository.class)).thenReturn(attachmentRepo);

        TenantContext.setCurrentTenant(TENANT_ID);
        CustomUserDetails userDetails = new CustomUserDetails(
                USER_ID, "testuser", "password",
                Collections.singletonList(new SimpleGrantedAuthority("work_order:execute")));
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(userDetails, null, userDetails.getAuthorities()));
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
        SecurityContextHolder.clearContext();
    }

    @Test
    void updateWorkOrderStatus_ShouldUpdateStatusAndSetActualStartTime_WhenStatusIsInprogress() {
        UUID workOrderId = UUID.randomUUID();
        WorkOrder workOrder = new WorkOrder();
        workOrder.setId(workOrderId);
        workOrder.setTenantId(TENANT_ID);
        workOrder.setStatus(WorkOrderStatus.ASSIGNED);
        workOrder.setAssignedTo(USER_ID);

        when(workOrderRepository.findByIdAndTenantId(workOrderId, TENANT_ID)).thenReturn(Optional.of(workOrder));
        when(workOrderRepository.save(any(WorkOrder.class))).thenReturn(workOrder);

        WorkOrderStatusUpdateRequest request = new WorkOrderStatusUpdateRequest();
        request.setStatus(WorkOrderStatus.IN_PROGRESS);

        WorkOrderDto dto = workOrderService.updateWorkOrderStatus(workOrderId, request);

        assertEquals(WorkOrderStatus.IN_PROGRESS, dto.getStatus());
        assertNotNull(dto.getActualStartTime());
        verify(workOrderRepository, times(1)).save(workOrder);
    }

    @Test
    void updateWorkOrderStatus_ShouldUpdateStatusAndEmitEvent_WhenStatusIsCompleted() throws Exception {
        UUID workOrderId = UUID.randomUUID();
        WorkOrder workOrder = new WorkOrder();
        workOrder.setId(workOrderId);
        workOrder.setTenantId(TENANT_ID);
        workOrder.setStatus(WorkOrderStatus.IN_PROGRESS);
        workOrder.setAssignedTo(USER_ID);
        workOrder.setResolutionNotes("Completed successfully");

        when(workOrderRepository.findByIdAndTenantId(workOrderId, TENANT_ID)).thenReturn(Optional.of(workOrder));
        when(workOrderRepository.save(any(WorkOrder.class))).thenReturn(workOrder);
        when(objectMapper.writeValueAsString(anyMap())).thenReturn("{}");

        WorkOrderStatusUpdateRequest request = new WorkOrderStatusUpdateRequest();
        request.setStatus(WorkOrderStatus.COMPLETED);

        WorkOrderDto dto = workOrderService.updateWorkOrderStatus(workOrderId, request);

        assertEquals(WorkOrderStatus.COMPLETED, dto.getStatus());
        assertNotNull(dto.getCompletedAt());
        verify(workOrderRepository, times(1)).save(workOrder);
        verify(kafkaTemplate, times(1)).send(eq("work_orders_topic"), eq("work_order.completed"), anyString());
    }

    @Test
    void updateWorkOrderStatus_ShouldThrowException_WhenInvalidStateTransition() {
        UUID workOrderId = UUID.randomUUID();
        WorkOrder workOrder = new WorkOrder();
        workOrder.setId(workOrderId);
        workOrder.setTenantId(TENANT_ID);
        workOrder.setStatus(WorkOrderStatus.CREATED);
        workOrder.setAssignedTo(USER_ID);

        when(workOrderRepository.findByIdAndTenantId(workOrderId, TENANT_ID)).thenReturn(Optional.of(workOrder));

        WorkOrderStatusUpdateRequest request = new WorkOrderStatusUpdateRequest();
        request.setStatus(WorkOrderStatus.IN_PROGRESS);

        assertThrows(IllegalArgumentException.class, () -> {
            workOrderService.updateWorkOrderStatus(workOrderId, request);
        });
        verify(workOrderRepository, never()).save(any());
    }

    @Test
    void getCalendarEvents_ShouldReturnWorkOrdersAndProjectedPmPlans() {
        ZonedDateTime start = ZonedDateTime.of(2026, 7, 1, 0, 0, 0, 0, ZoneOffset.UTC);
        ZonedDateTime end = ZonedDateTime.of(2026, 7, 31, 23, 59, 59, 0, ZoneOffset.UTC);

        // Mock WorkOrder
        WorkOrder wo = new WorkOrder();
        wo.setId(UUID.randomUUID());
        wo.setTitle("Test WO");
        wo.setDeadline(start.plusDays(5));
        wo.setStatus(WorkOrderStatus.CREATED);
        wo.setPriority("HIGH");
        Asset asset = new Asset();
        asset.setId(UUID.randomUUID());
        asset.setName("Test Asset");
        wo.setAsset(asset);

        when(workOrderRepository.findCalendarEventsByTenantId(TENANT_ID, start, end, null, null, null)).thenReturn(Arrays.asList(wo));

        // Mock PmPlanAssignment
        PmPlanAssignment assignment = new PmPlanAssignment();
        assignment.setId(UUID.randomUUID());
        assignment.setAsset(asset);
        PmPlan pmPlan = new PmPlan();
        pmPlan.setName("Monthly Maintenance");
        pmPlan.setTriggerType(PmTriggerType.TIME);
        pmPlan.setIntervalValue(java.math.BigDecimal.valueOf(1));
        pmPlan.setIntervalUnit(PmIntervalUnit.MONTHS);
        assignment.setPmPlan(pmPlan);
        assignment.setLastTriggeredAt(start.minusDays(5)); // Next trigger should be start.minusDays(5) + 1 month = around end.minusDays(5), which is in range

        when(pmPlanAssignmentRepository.findActiveAssignmentsByTenantId(TENANT_ID, null, null)).thenReturn(Arrays.asList(assignment));

        List<MaintenanceCalendarEventDto> events = workOrderService.getCalendarEvents(start, end, null, null, null);

        assertEquals(2, events.size(), "Should return 1 WorkOrder and 1 projected PM Plan");
        
        // Assert WO Event
        MaintenanceCalendarEventDto woEvent = events.stream().filter(e -> e.getEventType().equals("WORK_ORDER")).findFirst().orElseThrow();
        assertEquals(wo.getId().toString(), woEvent.getId());
        assertEquals("Test WO", woEvent.getTitle());

        // Assert PM Plan Event
        MaintenanceCalendarEventDto pmEvent = events.stream().filter(e -> e.getEventType().equals("PM_PLAN")).findFirst().orElseThrow();
        assertTrue(pmEvent.getId().startsWith(assignment.getId().toString() + "_proj"));
        assertEquals("PM: Monthly Maintenance", pmEvent.getTitle());
    }
}
