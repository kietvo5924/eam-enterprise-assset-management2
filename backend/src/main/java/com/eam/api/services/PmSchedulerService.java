package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.entities.PmPlan;
import com.eam.api.models.entities.PmPlanAssignment;
import com.eam.api.models.enums.PmTriggerType;
import com.eam.api.models.events.MaintenanceTriggeredEvent;
import com.eam.api.repositories.PmPlanAssignmentRepository;
import com.eam.api.repositories.MeterReadingRepository;
import com.eam.api.repositories.WorkOrderRepository;
import com.eam.api.models.entities.MeterReading;
import com.eam.api.models.entities.WorkOrder;
import com.eam.api.models.enums.WorkOrderStatus;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.Message;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.time.ZonedDateTime;
import java.util.List;
import java.util.concurrent.ExecutionException;

@Service
public class PmSchedulerService {

    private final PmPlanAssignmentRepository assignmentRepository;
    private final MeterReadingRepository meterReadingRepository;
    private final WorkOrderRepository workOrderRepository;
    private final KafkaTemplate<String, Object> kafkaTemplate;

    public PmSchedulerService(PmPlanAssignmentRepository assignmentRepository, 
                              MeterReadingRepository meterReadingRepository,
                              WorkOrderRepository workOrderRepository,
                              KafkaTemplate<String, Object> kafkaTemplate) {
        this.assignmentRepository = assignmentRepository;
        this.meterReadingRepository = meterReadingRepository;
        this.workOrderRepository = workOrderRepository;
        this.kafkaTemplate = kafkaTemplate;
    }

    @Scheduled(fixedRate = 60000) // Run every minute for MVP evaluation
    @Transactional
    public void evaluateTriggers() {
        List<PmPlanAssignment> activeAssignments = assignmentRepository.findAllActiveAssignments();

        ZonedDateTime now = ZonedDateTime.now();

        for (PmPlanAssignment assignment : activeAssignments) {
            PmPlan pmPlan = assignment.getPmPlan();
            boolean shouldTrigger = false;
            ZonedDateTime nextDueDate = now;

            if (pmPlan.getTriggerType() == PmTriggerType.TIME) {
                ZonedDateTime referenceDate = assignment.getLastTriggeredAt() != null 
                    ? assignment.getLastTriggeredAt() 
                    : assignment.getCreatedAt();
                
                String sourceReference = "PM_" + pmPlan.getId() + "_ASSET_" + assignment.getAsset().getId();
                
                // If Floating Schedule, find the last completed WO and use its completedAt as reference
                if (Boolean.TRUE.equals(pmPlan.getIsFloatingSchedule())) {
                    java.util.Optional<WorkOrder> lastCompletedWo = workOrderRepository.findFirstBySourceReferenceAndStatusOrderByCompletedAtDesc(sourceReference, WorkOrderStatus.COMPLETED);
                    if (lastCompletedWo.isPresent() && lastCompletedWo.get().getCompletedAt() != null) {
                        referenceDate = lastCompletedWo.get().getCompletedAt();
                    }
                }
                
                ZonedDateTime dueDate = referenceDate;
                if (pmPlan.getIntervalUnit() != null && pmPlan.getIntervalValue() != null) {
                    long interval = pmPlan.getIntervalValue().longValue();
                    if (interval == 0) {
                        continue; // Prevent infinite loop
                    }
                    switch (pmPlan.getIntervalUnit()) {
                        case DAYS: dueDate = referenceDate.plusDays(interval); break;
                        case WEEKS: dueDate = referenceDate.plusWeeks(interval); break;
                        case MONTHS: dueDate = referenceDate.plusMonths(interval); break;
                        case YEARS: dueDate = referenceDate.plusYears(interval); break;
                    }
                }
                
                ZonedDateTime generationDate = dueDate;
                if (pmPlan.getLeadTimeDays() != null && pmPlan.getLeadTimeDays() > 0) {
                    generationDate = dueDate.minusDays(pmPlan.getLeadTimeDays());
                }

                if (!generationDate.isAfter(now)) {
                    shouldTrigger = true;
                    nextDueDate = dueDate; // assignment lastTriggeredAt tracks the original due date
                }
            } else if (pmPlan.getTriggerType() == PmTriggerType.METER || pmPlan.getTriggerType() == PmTriggerType.USAGE) {
                // Fetch latest meter reading
                java.util.Optional<MeterReading> latestReadingOpt = meterReadingRepository.findFirstByAssetIdOrderByReadingDateDesc(assignment.getAsset().getId());
                
                if (latestReadingOpt.isPresent()) {
                    java.math.BigDecimal currentReading = latestReadingOpt.get().getReadingValue();
                    java.math.BigDecimal referenceReading = assignment.getLastTriggeredMeter() != null 
                        ? assignment.getLastTriggeredMeter() 
                        : (assignment.getBaselineMeterReading() != null ? assignment.getBaselineMeterReading() : java.math.BigDecimal.ZERO);
                        
                    java.math.BigDecimal threshold = pmPlan.getIntervalValue() != null ? pmPlan.getIntervalValue() : java.math.BigDecimal.ZERO;
                    
                    if (currentReading.subtract(referenceReading).compareTo(threshold) >= 0 && threshold.compareTo(java.math.BigDecimal.ZERO) > 0) {
                        shouldTrigger = true;
                        // For Meter/Usage, next due date is just now, as it exceeded the threshold
                        nextDueDate = now; 
                    }
                }
            }

            if (shouldTrigger) {
                String sourceReference = "PM_" + pmPlan.getId() + "_ASSET_" + assignment.getAsset().getId();
                
                // Check Suppress If Pending
                if (Boolean.TRUE.equals(pmPlan.getSuppressIfPending())) {
                    List<WorkOrderStatus> terminalStatuses = java.util.Arrays.asList(WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELED);
                    boolean hasPendingWo = workOrderRepository.existsBySourceReferenceAndStatusNotIn(sourceReference, terminalStatuses);
                    if (hasPendingWo) {
                        // Skip this cycle, do not update lastTriggeredAt
                        continue;
                    }
                }

                try {
                    TenantContext.setCurrentTenant(assignment.getTenantId());
                    
                    // Update assignment
                    assignment.setLastTriggeredAt(nextDueDate);
                    if (pmPlan.getTriggerType() == PmTriggerType.METER || pmPlan.getTriggerType() == PmTriggerType.USAGE) {
                        meterReadingRepository.findFirstByAssetIdOrderByReadingDateDesc(assignment.getAsset().getId())
                            .ifPresent(reading -> assignment.setLastTriggeredMeter(reading.getReadingValue()));
                    }
                    assignmentRepository.save(assignment);
    
                    // Publish Event
                    MaintenanceTriggeredEvent event = new MaintenanceTriggeredEvent(
                            assignment.getTenantId(),
                            assignment.getAsset().getId(),
                            pmPlan.getId(),
                            pmPlan.getTriggerType(),
                            "MEDIUM", // Default priority for PM
                            "PM: " + pmPlan.getName() + " for " + assignment.getAsset().getName(),
                            pmPlan.getDescription(),
                            nextDueDate // the actual deadline
                    );
                    
                    Message<MaintenanceTriggeredEvent> message = MessageBuilder
                        .withPayload(event)
                        .setHeader(KafkaHeaders.TOPIC, "maintenance.events")
                        .setHeader("X-Tenant-ID", event.getTenantId().getBytes(StandardCharsets.UTF_8))
                        .build();
                        
                    kafkaTemplate.send(message).get(); // Block to ensure send succeeds
                } catch (InterruptedException | ExecutionException e) {
                    throw new RuntimeException("Failed to send Kafka event, rolling back transaction", e);
                } finally {
                    TenantContext.clear();
                }
            }
        }
    }
}
