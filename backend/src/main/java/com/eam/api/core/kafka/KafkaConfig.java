package com.eam.api.core.kafka;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;

import jakarta.annotation.PostConstruct;

@Configuration
public class KafkaConfig {

    @Autowired
    private ConcurrentKafkaListenerContainerFactory<Object, Object> factory;

    @Autowired
    private TenantKafkaInterceptor<Object, Object> tenantKafkaInterceptor;

    @PostConstruct
    public void configureInterceptor() {
        factory.setRecordInterceptor(tenantKafkaInterceptor);
    }
}
