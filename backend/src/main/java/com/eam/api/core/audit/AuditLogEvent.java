package com.eam.api.core.audit;

import com.eam.api.models.entities.AuditLog;
import org.springframework.context.ApplicationEvent;

public class AuditLogEvent extends ApplicationEvent {
    private final AuditLog auditLog;

    public AuditLogEvent(AuditLog auditLog) {
        super(auditLog);
        this.auditLog = auditLog;
    }

    public AuditLog getAuditLog() {
        return auditLog;
    }
}
