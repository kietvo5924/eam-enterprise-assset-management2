package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.AssetCreateRequest;
import com.eam.api.models.dtos.AssetResponse;
import com.eam.api.models.dtos.AssetUpdateRequest;
import com.eam.api.models.entities.Asset;
import com.eam.api.models.enums.AssetStatus;
import com.eam.api.models.entities.AssetCategory;
import com.eam.api.models.entities.Location;
import com.eam.api.models.entities.HierarchyTemplate;
import com.eam.api.repositories.AssetCategoryRepository;
import com.eam.api.repositories.AssetRepository;
import com.eam.api.repositories.HierarchyTemplateRepository;
import com.eam.api.repositories.LocationRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.dao.DataIntegrityViolationException;
import jakarta.persistence.criteria.Predicate;

import com.eam.api.models.dtos.tree.AssetTreeResponse;
import com.eam.api.models.dtos.tree.LocationTreeNode;
import org.springframework.security.core.context.SecurityContextHolder;
import com.eam.api.core.security.CustomUserDetails;

import java.util.*;
import java.util.stream.Collectors;
import java.util.UUID;

@Service
public class AssetService {

    private final AssetRepository assetRepository;
    private final AssetCategoryRepository categoryRepository;
    private final LocationRepository locationRepository;
    private final HierarchyTemplateRepository templateRepository;

    public AssetService(AssetRepository assetRepository, AssetCategoryRepository categoryRepository,
            LocationRepository locationRepository, HierarchyTemplateRepository templateRepository) {
        this.assetRepository = assetRepository;
        this.categoryRepository = categoryRepository;
        this.locationRepository = locationRepository;
        this.templateRepository = templateRepository;
    }

    @Transactional(readOnly = true)
    public Page<AssetResponse> getAssets(Pageable pageable) {
        String tenantId = TenantContext.getCurrentTenant();
        return assetRepository.findByTenantIdAndIsActiveTrue(tenantId, pageable)
                .map(this::mapToDto);
    }

    @Transactional(readOnly = true)
    public AssetTreeResponse getAssetTree(String search, String status, UUID categoryId) {
        String tenantId = TenantContext.getCurrentTenant();

        // 1. Get all active locations
        List<Location> allLocations = locationRepository.findByTenantIdAndIsActiveTrue(tenantId, Pageable.unpaged())
                .getContent();

        // 2. Search assets using Criteria API
        Specification<Asset> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            predicates.add(cb.equal(root.get("tenantId"), tenantId));
            predicates.add(cb.isTrue(root.get("isActive")));

            if (status != null && !status.isEmpty()) {
                predicates.add(cb.equal(root.get("status"), AssetStatus.valueOf(status.toUpperCase())));
            }
            if (categoryId != null) {
                predicates.add(cb.equal(root.get("category").get("id"), categoryId));
            }

            return cb.and(predicates.toArray(new Predicate[0]));
        };

        List<Asset> filteredAssets = assetRepository.findAll(spec);

        // 3. Filter by search text (Asset fields OR Ancestor Location name)
        String searchLower = (search != null) ? search.toLowerCase() : null;

        Map<UUID, Location> locMap = allLocations.stream().collect(Collectors.toMap(Location::getId, l -> l));

        List<AssetResponse> matchingAssets = new ArrayList<>();
        for (Asset a : filteredAssets) {
            boolean matches = true;
            if (searchLower != null && !searchLower.isEmpty()) {
                boolean assetMatches = (a.getName() != null && a.getName().toLowerCase().contains(searchLower)) ||
                        (a.getSerialNumber() != null && a.getSerialNumber().toLowerCase().contains(searchLower)) ||
                        (a.getQrCode() != null && a.getQrCode().toLowerCase().contains(searchLower));

                if (!assetMatches) {
                    boolean ancestorMatches = false;
                    Location loc = a.getLocation();
                    while (loc != null) {
                        if (loc.getName().toLowerCase().contains(searchLower)) {
                            ancestorMatches = true;
                            break;
                        }
                        if (loc.getParentId() != null) {
                            String parentIdPath = loc.getParentId();
                            // In this simple implementation, we find parent by matching full path string
                            // (ltree logic)
                            // A better way is storing parent UUID, but here we scan allLocations matching
                            // getFullPath
                            String finalPath = parentIdPath;
                            loc = allLocations.stream().filter(l -> {
                                String lFullPath = l.getParentId() != null
                                        ? l.getParentId() + "." + formatLtree(l.getName())
                                        : formatLtree(l.getName());
                                return lFullPath.equals(finalPath);
                            }).findFirst().orElse(null);
                        } else {
                            loc = null;
                        }
                    }
                    if (!ancestorMatches)
                        matches = false;
                }
            }
            if (matches) {
                matchingAssets.add(mapToDto(a));
            }
        }

        // 4. Determine visible locations based on matching assets and search text
        Set<UUID> visibleLocIds = new HashSet<>();

        // Add locations that contain matching assets or their ancestors
        for (AssetResponse a : matchingAssets) {
            if (a.locationId() != null) {
                Location loc = locMap.get(a.locationId());
                while (loc != null) {
                    visibleLocIds.add(loc.getId());
                    if (loc.getParentId() != null) {
                        String finalPath = loc.getParentId();
                        loc = allLocations.stream().filter(l -> {
                            String lFullPath = l.getParentId() != null
                                    ? l.getParentId() + "." + formatLtree(l.getName())
                                    : formatLtree(l.getName());
                            return lFullPath.equals(finalPath);
                        }).findFirst().orElse(null);
                    } else {
                        loc = null;
                    }
                }
            }
        }

        // Add locations matching search text directly
        if (searchLower != null && !searchLower.isEmpty()) {
            for (Location loc : allLocations) {
                if (loc.getName().toLowerCase().contains(searchLower)) {
                    Location curr = loc;
                    while (curr != null) {
                        visibleLocIds.add(curr.getId());
                        if (curr.getParentId() != null) {
                            String finalPath = curr.getParentId();
                            curr = allLocations.stream().filter(l -> {
                                String lFullPath = l.getParentId() != null
                                        ? l.getParentId() + "." + formatLtree(l.getName())
                                        : formatLtree(l.getName());
                                return lFullPath.equals(finalPath);
                            }).findFirst().orElse(null);
                        } else {
                            curr = null;
                        }
                    }
                }
            }
        } else {
            // If no search and no filter, all locations are visible
            if (status == null && categoryId == null) {
                allLocations.forEach(l -> visibleLocIds.add(l.getId()));
            }
        }

        // 5. Build Tree
        List<LocationTreeNode> rootNodes = new ArrayList<>();
        Map<UUID, LocationTreeNode> nodeMap = new HashMap<>();

        for (Location loc : allLocations) {
            if (!visibleLocIds.contains(loc.getId()))
                continue;

            List<AssetResponse> locAssets = matchingAssets.stream()
                    .filter(a -> loc.getId().equals(a.locationId()))
                    .collect(Collectors.toList());

            LocationTreeNode node = new LocationTreeNode(
                    loc.getId(),
                    loc.getName(),
                    loc.getParentId(),
                    loc.getIsActive(),
                    locAssets,
                    new ArrayList<>());
            nodeMap.put(loc.getId(), node);
        }

        for (Location loc : allLocations) {
            if (!visibleLocIds.contains(loc.getId()))
                continue;

            LocationTreeNode node = nodeMap.get(loc.getId());
            if (loc.getParentId() == null || loc.getParentId().isEmpty()) {
                rootNodes.add(node);
            } else {
                // Find parent node
                LocationTreeNode parentNode = null;
                for (Location pLoc : allLocations) {
                    if (visibleLocIds.contains(pLoc.getId())) {
                        String pFullPath = pLoc.getParentId() != null
                                ? pLoc.getParentId() + "." + formatLtree(pLoc.getName())
                                : formatLtree(pLoc.getName());
                        if (pFullPath.equals(loc.getParentId())) {
                            parentNode = nodeMap.get(pLoc.getId());
                            break;
                        }
                    }
                }
                if (parentNode != null) {
                    parentNode.children().add(node);
                } else {
                    rootNodes.add(node); // Fallback if parent missing or filtered
                }
            }
        }

        List<AssetResponse> unassignedAssets = matchingAssets.stream()
                .filter(a -> a.locationId() == null)
                .collect(Collectors.toList());

        return new AssetTreeResponse(rootNodes, unassignedAssets);
    }

    private String formatLtree(String s) {
        if (s == null)
            return "";
        String normalized = java.text.Normalizer.normalize(s, java.text.Normalizer.Form.NFD)
                .replaceAll("[\\p{InCombiningDiacriticalMarks}]", "");
        String ltree = normalized.replaceAll("[^a-zA-Z0-9.]", "_");
        ltree = ltree.replaceAll("_+", "_").replaceAll("\\.+", ".");
        ltree = ltree.replaceAll("^[_.]+|[_.]+$", "");
        return ltree;
    }

    @Transactional(readOnly = true)
    public AssetResponse getAssetById(UUID id) {
        return mapToDto(findByIdAndTenantId(id));
    }

    @Transactional(readOnly = true)
    public AssetResponse getAssetByQrCode(String qrCode) {
        String tenantId = TenantContext.getCurrentTenant();
        Asset asset = assetRepository.findByQrCodeAndTenantIdAndIsActiveTrue(qrCode, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Asset not found with QR code: " + qrCode));
        return mapToDto(asset);
    }

    @Transactional
    public AssetResponse createAsset(AssetCreateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();

        Asset asset = new Asset();
        asset.setTenantId(tenantId);
        asset.setName(request.name());

        UUID currentUserId = getCurrentUserId();
        asset.setCreatedBy(currentUserId);
        asset.setUpdatedBy(currentUserId);

        if (request.categoryId() != null) {
            AssetCategory category = categoryRepository.findByIdAndTenantId(request.categoryId(), tenantId)
                    .orElseThrow(() -> new IllegalArgumentException("Asset category not found"));
            asset.setCategory(category);
        }

        asset.setSerialNumber(request.serialNumber());
        asset.setModel(request.model());
        asset.setManufacturer(request.manufacturer());
        asset.setPurchaseDate(request.purchaseDate());
        asset.setValue(request.value());
        asset.setStatus(request.status() != null ? request.status() : AssetStatus.OPERATIONAL);
        if (request.locationId() != null) {
            Location location = locationRepository.findByIdAndTenantId(request.locationId(), tenantId)
                    .orElseThrow(() -> new IllegalArgumentException("Location not found"));
            asset.setLocation(location);
        } else {
            asset.setLocation(null);
        }

        if (request.hierarchyTemplateId() != null) {
            HierarchyTemplate template = templateRepository.findByIdAndTenantId(request.hierarchyTemplateId(), tenantId)
                    .orElseThrow(() -> new IllegalArgumentException("Hierarchy Template not found"));
            asset.setHierarchyTemplate(template);
        } else {
            asset.setHierarchyTemplate(null);
        }

        asset.setIsActive(request.isActive() != null ? request.isActive() : true);

        // Generate unique QR code
        String qrCode = "AST-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
        while (assetRepository.existsByQrCodeAndTenantId(qrCode, tenantId)) {
            qrCode = "AST-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
        }
        asset.setQrCode(qrCode);

        try {
            return mapToDto(assetRepository.save(asset));
        } catch (DataIntegrityViolationException e) {
            throw new IllegalArgumentException("Failed to save asset due to data integrity violation");
        }
    }

    @Transactional
    public AssetResponse updateAsset(UUID id, AssetUpdateRequest request) {
        String tenantId = TenantContext.getCurrentTenant();
        Asset asset = findByIdAndTenantId(id);

        asset.setName(request.name());
        asset.setUpdatedBy(getCurrentUserId());

        if (request.categoryId() != null) {
            if (asset.getCategory() == null || !asset.getCategory().getId().equals(request.categoryId())) {
                AssetCategory category = categoryRepository.findByIdAndTenantId(request.categoryId(), tenantId)
                        .orElseThrow(() -> new IllegalArgumentException("Asset category not found"));
                asset.setCategory(category);
            }
        } else {
            asset.setCategory(null);
        }

        asset.setSerialNumber(request.serialNumber());
        asset.setModel(request.model());
        asset.setManufacturer(request.manufacturer());
        asset.setPurchaseDate(request.purchaseDate());
        asset.setValue(request.value());
        if (request.status() != null)
            asset.setStatus(request.status());

        if (request.locationId() != null) {
            if (asset.getLocation() == null || !asset.getLocation().getId().equals(request.locationId())) {
                Location location = locationRepository.findByIdAndTenantId(request.locationId(), tenantId)
                        .orElseThrow(() -> new IllegalArgumentException("Location not found"));
                asset.setLocation(location);
            }
        } else {
            asset.setLocation(null);
        }

        if (request.hierarchyTemplateId() != null) {
            if (asset.getHierarchyTemplate() == null
                    || !asset.getHierarchyTemplate().getId().equals(request.hierarchyTemplateId())) {
                HierarchyTemplate template = templateRepository
                        .findByIdAndTenantId(request.hierarchyTemplateId(), tenantId)
                        .orElseThrow(() -> new IllegalArgumentException("Hierarchy Template not found"));
                asset.setHierarchyTemplate(template);
            }
        } else {
            asset.setHierarchyTemplate(null);
        }

        if (request.isActive() != null)
            asset.setIsActive(request.isActive());

        return mapToDto(assetRepository.save(asset));
    }

    @Transactional
    public void deleteAsset(UUID id) {
        Asset asset = findByIdAndTenantId(id);
        asset.setIsActive(false);
        assetRepository.save(asset);
    }

    private Asset findByIdAndTenantId(UUID id) {
        String tenantId = TenantContext.getCurrentTenant();
        return assetRepository.findByIdAndTenantIdAndIsActiveTrue(id, tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Asset not found with id: " + id));
    }

    private UUID getCurrentUserId() {
        if (SecurityContextHolder.getContext().getAuthentication() != null) {
            Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
            if (principal instanceof CustomUserDetails) {
                return ((CustomUserDetails) principal).getId();
            }
        }
        return null;
    }

    private AssetResponse mapToDto(Asset asset) {
        return new AssetResponse(
                asset.getId(),
                asset.getName(),
                asset.getCategory() != null ? asset.getCategory().getId() : null,
                asset.getCategory() != null ? asset.getCategory().getName() : null,
                asset.getParentId(),
                asset.getSerialNumber(),
                asset.getModel(),
                asset.getManufacturer(),
                asset.getPurchaseDate(),
                asset.getValue(),
                asset.getStatus(),
                asset.getLocation() != null ? asset.getLocation().getId() : null,
                asset.getLocation() != null ? asset.getLocation().getName() : null,
                asset.getHierarchyTemplate() != null ? asset.getHierarchyTemplate().getId() : null,
                asset.getHierarchyTemplate() != null ? asset.getHierarchyTemplate().getName() : null,
                asset.getQrCode(),
                asset.getIsActive(),
                asset.getCreatedAt(),
                asset.getUpdatedAt(),
                asset.getCreator() != null ? asset.getCreator().getUsername() : null,
                asset.getUpdater() != null ? asset.getUpdater().getUsername() : null);
    }
}
