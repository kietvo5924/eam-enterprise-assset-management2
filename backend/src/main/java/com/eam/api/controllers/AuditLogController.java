package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.AuditLogDto;
import com.eam.api.models.enums.ActionType;
import com.eam.api.services.AuditLogService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.time.ZonedDateTime;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/audit-logs")
public class AuditLogController {

    @Autowired
    private AuditLogService auditLogService;

    @GetMapping
    @PreAuthorize("hasAuthority('audit_logs:read')")
    public ApiResponse<Map<String, Object>> getAuditLogs(
            @RequestParam(required = false) String username,
            @RequestParam(required = false) ActionType actionType,
            @RequestParam(required = false) String entityType,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) ZonedDateTime startDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) ZonedDateTime endDate,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "timestamp") String sortBy,
            @RequestParam(defaultValue = "DESC") String sortDir) {
        
        Sort.Direction direction = Sort.Direction.fromString(sortDir);
        Pageable pageable = PageRequest.of(page, size, Sort.by(direction, sortBy));

        Page<AuditLogDto> logs = auditLogService.getAuditLogs(username, actionType, entityType, startDate, endDate, pageable);
        
        Map<String, Object> response = new HashMap<>();
        response.put("content", logs.getContent());
        response.put("currentPage", logs.getNumber());
        response.put("totalElements", logs.getTotalElements());
        response.put("totalPages", logs.getTotalPages());
        
        return ApiResponse.success(response);
    }
}
