package com.eam.api.services;

// removed custom exceptions
import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.AssetCategoryCreateRequest;
import com.eam.api.models.dtos.AssetCategoryDto;
import com.eam.api.models.dtos.AssetCategoryUpdateRequest;
import com.eam.api.models.entities.AssetCategory;
import com.eam.api.repositories.AssetCategoryRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import org.springframework.dao.DataIntegrityViolationException;

import java.util.UUID;

@Service
public class AssetCategoryService {

    private final AssetCategoryRepository categoryRepository;

    public AssetCategoryService(AssetCategoryRepository categoryRepository) {
        this.categoryRepository = categoryRepository;
    }

    @Transactional(readOnly = true)
    public Page<AssetCategoryDto> getCategories(Pageable pageable) {
        String tenantId = TenantContext.getCurrentTenant();
        return categoryRepository.findByTenantId(tenantId, pageable)
                .map(this::mapToDto);
    }

    @Transactional(readOnly = true)
    public AssetCategoryDto getCategoryById(UUID id) {
        return mapToDto(findByIdAndTenantId(id));
    }

    @Transactional
    public AssetCategoryDto createCategory(AssetCategoryCreateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        if (categoryRepository.existsByNameAndTenantId(request.name(), tenantId)) {
            throw new IllegalArgumentException("Category name already exists in this tenant");
        }

        AssetCategory category = new AssetCategory();
        category.setTenantId(tenantId);
        category.setName(request.name());
        category.setDescription(request.description());
        category.setIsActive(request.isActive() != null ? request.isActive() : true);

        try {
            return mapToDto(categoryRepository.save(category));
        } catch (DataIntegrityViolationException e) {
            throw new IllegalArgumentException("Category name already exists in this tenant");
        }
    }

    @Transactional
    public AssetCategoryDto updateCategory(UUID id, AssetCategoryUpdateRequest request) {
        AssetCategory category = findByIdAndTenantId(id);
        
        if (!category.getName().equals(request.name()) && 
            categoryRepository.existsByNameAndTenantId(request.name(), category.getTenantId())) {
            throw new IllegalArgumentException("Category name already exists in this tenant");
        }

        category.setName(request.name());
        category.setDescription(request.description());
        if (request.isActive() != null) {
            category.setIsActive(request.isActive());
        }

        try {
            return mapToDto(categoryRepository.save(category));
        } catch (DataIntegrityViolationException e) {
            throw new IllegalArgumentException("Category name already exists in this tenant");
        }
    }

    @Transactional
    public void deleteCategory(UUID id) {
        AssetCategory category = findByIdAndTenantId(id);
        category.setIsActive(false);
        categoryRepository.save(category);
    }

    private AssetCategory findByIdAndTenantId(UUID id) {
        String tenantId = TenantContext.getCurrentTenant();
        return categoryRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Asset category not found with id: " + id));
    }

    private AssetCategoryDto mapToDto(AssetCategory category) {
        return new AssetCategoryDto(
                category.getId(),
                category.getTenantId(),
                category.getName(),
                category.getDescription(),
                category.getIsActive(),
                category.getCreatedAt(),
                category.getUpdatedAt()
        );
    }
}
