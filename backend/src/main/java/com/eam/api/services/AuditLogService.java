package com.eam.api.services;

import com.eam.api.models.entities.AuditLog;
import com.eam.api.models.enums.ActionType;
import com.eam.api.repositories.AuditLogRepository;
import com.eam.api.models.dtos.AuditLogDto;
import com.eam.api.models.entities.User;
import com.eam.api.repositories.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import jakarta.persistence.criteria.Predicate;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class AuditLogService {

    @Autowired
    private AuditLogRepository auditLogRepository;
    
    @Autowired
    private UserRepository userRepository;

    public void logAction(ActionType actionType, String entityType, String entityId) {
        AuditLog log = new AuditLog();
        log.setActionType(actionType);
        log.setEntityType(entityType);
        log.setEntityId(entityId);
        try {
            org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
            if (auth != null && auth.isAuthenticated()) {
                String username = auth.getName();
                String tenantId = com.eam.api.core.tenant.TenantContext.getCurrentTenant();
                log.setTenantId(tenantId);
                java.util.Optional<com.eam.api.models.entities.User> user = userRepository.findByUsernameAndTenantId(username, tenantId);
                if (user.isPresent()) {
                    log.setUserId(user.get().getId().toString());
                } else {
                    log.setUserId("system");
                }
            } else {
                log.setUserId("system");
                log.setTenantId(com.eam.api.core.tenant.TenantContext.getCurrentTenant());
            }
        } catch (Exception e) {
            log.setUserId("system");
            log.setTenantId(com.eam.api.core.tenant.TenantContext.getCurrentTenant());
        }
        auditLogRepository.save(log);
    }

    public Page<AuditLogDto> getAuditLogs(String username, ActionType actionType, String entityType, ZonedDateTime startDate, ZonedDateTime endDate, Pageable pageable) {
        
        List<String> searchUserIds = null;
        if (username != null && !username.trim().isEmpty()) {
            searchUserIds = userRepository.findByUsernameContainingIgnoreCase(username.trim())
                    .stream()
                    .map(u -> u.getId().toString())
                    .collect(Collectors.toList());
                    
            boolean isSystemSearch = "system".contains(username.trim().toLowerCase());
            
            if (searchUserIds.isEmpty() && !isSystemSearch) {
                return Page.empty(pageable);
            }
            if (isSystemSearch) {
                searchUserIds.add("system");
            }
        }
        
        final List<String> finalSearchUserIds = searchUserIds;

        Specification<AuditLog> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            
            if (finalSearchUserIds != null) {
                predicates.add(root.get("userId").in(finalSearchUserIds));
            }
            if (actionType != null) {
                predicates.add(cb.equal(root.get("actionType"), actionType));
            }
            if (entityType != null && !entityType.isEmpty()) {
                predicates.add(cb.equal(root.get("entityType"), entityType));
            }
            if (startDate != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("timestamp"), startDate));
            }
            if (endDate != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("timestamp"), endDate));
            }
            
            return cb.and(predicates.toArray(new Predicate[0]));
        };
        
        Page<AuditLog> logs = auditLogRepository.findAll(spec, pageable);
        
        // Collect all distinct user IDs
        List<UUID> userIds = logs.getContent().stream()
            .map(AuditLog::getUserId)
            .filter(id -> id != null && !id.equals("system") && !id.equals("unknown"))
            .map(id -> {
                try {
                    return UUID.fromString(id);
                } catch (Exception e) {
                    return null;
                }
            })
            .filter(id -> id != null)
            .distinct()
            .collect(Collectors.toList());
            
        // Fetch usernames efficiently
        Map<String, String> usernameMap = userRepository.findAllById(userIds).stream()
            .collect(Collectors.toMap(u -> u.getId().toString(), User::getUsername));
            
        return logs.map(log -> {
            AuditLogDto dto = new AuditLogDto();
            dto.setId(log.getId().toString());
            dto.setTenantId(log.getTenantId());
            dto.setUserId(log.getUserId());
            dto.setActionType(log.getActionType());
            dto.setEntityType(log.getEntityType());
            dto.setEntityId(log.getEntityId());
            dto.setTimestamp(log.getTimestamp());
            
            if ("system".equals(log.getUserId())) {
                dto.setUsername("System Account");
            } else {
                dto.setUsername(usernameMap.getOrDefault(log.getUserId(), "Unknown User"));
            }
            
            return dto;
        });
    }
}
