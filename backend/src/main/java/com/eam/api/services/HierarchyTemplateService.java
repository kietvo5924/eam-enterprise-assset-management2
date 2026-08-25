package com.eam.api.services;

// removed custom exceptions
import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.HierarchyTemplateCreateRequest;
import com.eam.api.models.dtos.HierarchyTemplateDto;
import com.eam.api.models.dtos.HierarchyTemplateUpdateRequest;
import com.eam.api.models.entities.HierarchyTemplate;
import com.eam.api.repositories.HierarchyTemplateRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.dao.DataIntegrityViolationException;

import java.util.UUID;

@Service
public class HierarchyTemplateService {

    private final HierarchyTemplateRepository templateRepository;

    public HierarchyTemplateService(HierarchyTemplateRepository templateRepository) {
        this.templateRepository = templateRepository;
    }

    @Transactional(readOnly = true)
    public Page<HierarchyTemplateDto> getTemplates(Pageable pageable) {
        String tenantId = TenantContext.getCurrentTenant();
        return templateRepository.findByTenantIdOrderByPathAsc(tenantId, pageable)
                .map(this::mapToDto);
    }

    @Transactional(readOnly = true)
    public HierarchyTemplateDto getTemplateById(UUID id) {
        return mapToDto(findByIdAndTenantId(id));
    }

    @Transactional
    public HierarchyTemplateDto createTemplate(HierarchyTemplateCreateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        if (templateRepository.existsByNameAndTenantId(request.name(), tenantId)) {
            throw new IllegalArgumentException("Hierarchy template name already exists in this tenant");
        }

        HierarchyTemplate template = new HierarchyTemplate();
        template.setTenantId(tenantId);
        template.setName(request.name());
        template.setPath(request.path());
        template.setDescription(request.description());
        template.setIsActive(request.isActive() != null ? request.isActive() : true);

        try {
            return mapToDto(templateRepository.save(template));
        } catch (DataIntegrityViolationException e) {
            throw new IllegalArgumentException("Hierarchy template name already exists in this tenant");
        }
    }

    @Transactional
    public HierarchyTemplateDto updateTemplate(UUID id, HierarchyTemplateUpdateRequest request) {
        HierarchyTemplate template = findByIdAndTenantId(id);

        if (!template.getName().equals(request.name()) &&
                templateRepository.existsByNameAndTenantId(request.name(), template.getTenantId())) {
            throw new IllegalArgumentException("Hierarchy template name already exists in this tenant");
        }

        template.setName(request.name());
        if (request.path() != null) {
            template.setPath(request.path());
        }
        template.setDescription(request.description());
        if (request.isActive() != null) {
            template.setIsActive(request.isActive());
        }

        try {
            return mapToDto(templateRepository.save(template));
        } catch (DataIntegrityViolationException e) {
            throw new IllegalArgumentException("Hierarchy template name already exists in this tenant");
        }
    }

    @Transactional
    public void deleteTemplate(UUID id) {
        HierarchyTemplate template = findByIdAndTenantId(id);
        template.setIsActive(false);
        templateRepository.save(template);
    }

    private HierarchyTemplate findByIdAndTenantId(UUID id) {
        String tenantId = TenantContext.getCurrentTenant();
        return templateRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Hierarchy template not found with id: " + id));
    }

    private HierarchyTemplateDto mapToDto(HierarchyTemplate template) {
        return new HierarchyTemplateDto(
                template.getId(),
                template.getTenantId(),
                template.getName(),
                template.getPath(),
                template.getDescription(),
                template.getIsActive(),
                template.getCreatedAt(),
                template.getUpdatedAt());
    }
}
