package com.eam.api.services;

import com.eam.api.models.events.MaintenanceTriggeredEvent;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class WorkOrderKafkaConsumer {

    private final WorkOrderService workOrderService;

    public WorkOrderKafkaConsumer(WorkOrderService workOrderService) {
        this.workOrderService = workOrderService;
    }

    @KafkaListener(topics = "maintenance.events", groupId = "workorder-group")
    @Transactional
    public void handleMaintenanceTriggeredEvent(MaintenanceTriggeredEvent event) {
        workOrderService.generateFromPmPlan(event);
    }
}
