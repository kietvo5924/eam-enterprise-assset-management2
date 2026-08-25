package com.eam.api.core.tenant;

import jakarta.persistence.EntityManager;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Before;
import org.hibernate.Session;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Aspect
@Component
public class TenantFilterAspect {

    @Autowired
    private EntityManager entityManager;

    @Before("(execution(* org.springframework.data.repository.Repository+.*(..)) || execution(* com.eam.api..*Repository+.*(..))) && !target(com.eam.api.repositories.TenantRepository)")
    public void enableTenantFilter() {
        org.springframework.web.context.request.ServletRequestAttributes attributes = (org.springframework.web.context.request.ServletRequestAttributes) org.springframework.web.context.request.RequestContextHolder.getRequestAttributes();
        if (attributes != null) {
            jakarta.servlet.http.HttpServletRequest request = attributes.getRequest();
            String uri = request.getRequestURI();
            System.out.println("TENANT FILTER ASPECT - URI: " + uri);
            if (uri.startsWith("/api/v1/system") || 
                uri.startsWith("/api/v1/auth/forgot-password") || 
                uri.startsWith("/api/v1/auth/reset-password") ||
                uri.startsWith("/api/v1/auth/accept-invite")) {
                return; // Bypass for system API and specific auth APIs
            }
        }

        String tenantId = TenantContext.getCurrentTenant();
        if (tenantId != null) {
            Session session = entityManager.unwrap(Session.class);
            session.enableFilter("tenantFilter").setParameter("tenantId", tenantId);
        } else {
            if (attributes == null) {
                // Background thread (Scheduler, Kafka Consumer, etc)
                return;
            }
            throw new IllegalStateException("Tenant context is missing! A valid tenant_id is required to access data.");
        }
    }
}
