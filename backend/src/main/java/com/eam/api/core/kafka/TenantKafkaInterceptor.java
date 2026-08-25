package com.eam.api.core.kafka;

import com.eam.api.core.tenant.TenantContext;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.header.Header;
import org.springframework.kafka.listener.RecordInterceptor;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;

@Component
public class TenantKafkaInterceptor<K, V> implements RecordInterceptor<K, V> {

    public static final String TENANT_HEADER = "X-Tenant-ID";

    @Override
    public ConsumerRecord<K, V> intercept(ConsumerRecord<K, V> record, Consumer<K, V> consumer) {
        Header tenantHeader = record.headers().lastHeader(TENANT_HEADER);
        if (tenantHeader != null) {
            String tenantId = new String(tenantHeader.value(), StandardCharsets.UTF_8);
            TenantContext.setCurrentTenant(tenantId);
        }
        return record;
    }

    @Override
    public void success(ConsumerRecord<K, V> record, Consumer<K, V> consumer) {
        TenantContext.clear();
    }

    @Override
    public void failure(ConsumerRecord<K, V> record, Exception exception, Consumer<K, V> consumer) {
        TenantContext.clear();
    }
}
