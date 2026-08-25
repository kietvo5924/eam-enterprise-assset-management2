package com.eam.api.models.dtos;

import java.time.ZonedDateTime;
import java.util.UUID;

public class MaintenanceCalendarEventDto {
    private String id; // WO UUID or PM Plan Assignment ID + suffix
    private String title;
    private ZonedDateTime eventDate;
    private String eventType; // "WORK_ORDER" or "PM_PLAN"
    private String status; // WorkOrderStatus or "SCHEDULED"
    private UUID assetId;
    private String assetName;
    private String priority;
    private Object originalData;
    
    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    
    public ZonedDateTime getEventDate() { return eventDate; }
    public void setEventDate(ZonedDateTime eventDate) { this.eventDate = eventDate; }
    
    public String getEventType() { return eventType; }
    public void setEventType(String eventType) { this.eventType = eventType; }
    
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    
    public UUID getAssetId() { return assetId; }
    public void setAssetId(UUID assetId) { this.assetId = assetId; }
    
    public String getAssetName() { return assetName; }
    public void setAssetName(String assetName) { this.assetName = assetName; }

    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }

    public Object getOriginalData() { return originalData; }
    public void setOriginalData(Object originalData) { this.originalData = originalData; }
}
