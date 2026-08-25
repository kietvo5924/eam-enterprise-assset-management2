package com.eam.api.core.tenant;

public class TenantContext {
    private static final ThreadLocal<String> CURRENT_TENANT = new InheritableThreadLocal<>();

    public static String getCurrentTenant() {
        return CURRENT_TENANT.get();
    }

    public static void setCurrentTenant(String tenant) {
        CURRENT_TENANT.set(tenant);
    }

    public static void clear() {
        CURRENT_TENANT.remove();
    }
}
