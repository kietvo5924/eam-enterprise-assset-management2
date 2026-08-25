package com.eam.api.core.audit;

import com.eam.api.core.security.CustomUserDetails;
import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.entities.AuditLog;
import com.eam.api.models.enums.ActionType;
import jakarta.persistence.PostPersist;
import jakarta.persistence.PostRemove;
import jakarta.persistence.PostUpdate;
import org.springframework.context.ApplicationContext;
import org.springframework.context.ApplicationContextAware;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

@Component
public class AuditTrailListener implements ApplicationContextAware {

    private static ApplicationContext context;

    @Override
    public void setApplicationContext(ApplicationContext applicationContext) {
        context = applicationContext;
    }

    @PostPersist
    public void onPostPersist(Object entity) {
        publishEvent(entity, ActionType.CREATE);
    }

    @PostUpdate
    public void onPostUpdate(Object entity) {
        publishEvent(entity, ActionType.UPDATE);
    }

    @PostRemove
    public void onPostRemove(Object entity) {
        publishEvent(entity, ActionType.DELETE);
    }

    private void publishEvent(Object entity, ActionType actionType) {
        if (entity instanceof AuditLog) return;

        String tenantId = TenantContext.getCurrentTenant();
        if (tenantId == null) {
            System.out.println("AuditTrailListener: tenantId is null, skipping audit for " + entity.getClass().getSimpleName());
            return;
        }

        String userId = "system";
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof CustomUserDetails) {
            userId = ((CustomUserDetails) auth.getPrincipal()).getId().toString();
        }

        String entityId = extractEntityId(entity);
        String entityType = entity.getClass().getSimpleName();

        AuditLog log = new AuditLog();
        log.setTenantId(tenantId);
        log.setUserId(userId);
        log.setActionType(actionType);
        log.setEntityType(entityType);
        log.setEntityId(entityId);

        if (context != null) {
            System.out.println("AuditTrailListener: publishing event for " + actionType + " " + entityType);
            context.publishEvent(new AuditLogEvent(log));
        } else {
            System.out.println("AuditTrailListener: CONTEXT IS NULL, cannot publish event!");
        }
    }

    private String extractEntityId(Object entity) {
        try {
            java.lang.reflect.Method getIdMethod = entity.getClass().getMethod("getId");
            Object id = getIdMethod.invoke(entity);
            return id != null ? id.toString() : "unknown";
        } catch (Exception e) {
            return "unknown";
        }
    }
}
