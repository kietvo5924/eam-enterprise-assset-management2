package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.AssetImportResultDto;
import com.eam.api.models.entities.*;
import com.eam.api.models.enums.AssetStatus;
import com.eam.api.repositories.*;
import com.opencsv.CSVReader;
import com.opencsv.CSVWriter;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import jakarta.servlet.http.HttpServletResponse;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;

@Service
public class AssetImportExportService {

    @Autowired
    private AssetRepository assetRepository;
    @Autowired
    private AssetCategoryRepository categoryRepository;
    @Autowired
    private LocationRepository locationRepository;
    @Autowired
    private HierarchyTemplateRepository templateRepository;

    @Transactional
    public AssetImportResultDto importAssets(MultipartFile file) {
        String tenantId = TenantContext.getCurrentTenant();
        int successCount = 0;
        int failureCount = 0;
        List<String> errors = new ArrayList<>();

        Map<String, AssetCategory> categoryMap = new HashMap<>();
        categoryRepository.findByTenantId(tenantId).forEach(c -> categoryMap.put(c.getName(), c));

        Map<String, Location> locationMap = new HashMap<>();
        locationRepository.findByTenantId(tenantId).forEach(l -> locationMap.put(l.getName(), l));

        Map<String, HierarchyTemplate> templateMap = new HashMap<>();
        templateRepository.findByTenantId(tenantId).forEach(t -> templateMap.put(t.getName(), t));

        List<Asset> assetsToSave = new ArrayList<>();

        try (CSVReader reader = new CSVReader(new BufferedReader(new InputStreamReader(file.getInputStream())))) {
            String[] line;
            int lineNumber = 0;
            boolean isFirst = true;

            while ((line = reader.readNext()) != null) {
                lineNumber++;
                if (isFirst) {
                    isFirst = false;
                    continue;
                }
                
                if (line.length == 0 || (line.length == 1 && line[0].trim().isEmpty())) continue;

                if (line.length < 1) {
                    failureCount++;
                    errors.add("Line " + lineNumber + ": Missing asset name");
                    continue;
                }

                String name = line[0].trim();
                if (name.isEmpty()) {
                    failureCount++;
                    errors.add("Line " + lineNumber + ": Asset name cannot be empty");
                    continue;
                }

                Asset asset = new Asset();
                asset.setTenantId(tenantId);
                asset.setName(name);

                if (line.length > 1 && !line[1].trim().isEmpty()) {
                    AssetCategory cat = categoryMap.get(line[1].trim());
                    if (cat != null) asset.setCategory(cat);
                }

                if (line.length > 2 && !line[2].trim().isEmpty()) {
                    HierarchyTemplate tmp = templateMap.get(line[2].trim());
                    if (tmp != null) asset.setHierarchyTemplate(tmp);
                }

                if (line.length > 3) asset.setSerialNumber(line[3].trim());
                if (line.length > 4) asset.setModel(line[4].trim());
                if (line.length > 5) asset.setManufacturer(line[5].trim());

                if (line.length > 6 && !line[6].trim().isEmpty()) {
                    try {
                        asset.setPurchaseDate(LocalDate.parse(line[6].trim()));
                    } catch (Exception e) {}
                }

                if (line.length > 7 && !line[7].trim().isEmpty()) {
                    try {
                        asset.setValue(new BigDecimal(line[7].trim()));
                    } catch (Exception e) {}
                }

                if (line.length > 8 && !line[8].trim().isEmpty()) {
                    try {
                        asset.setStatus(AssetStatus.valueOf(line[8].trim().toUpperCase()));
                    } catch (IllegalArgumentException e) {
                        asset.setStatus(AssetStatus.OPERATIONAL);
                    }
                } else {
                    asset.setStatus(AssetStatus.OPERATIONAL);
                }

                if (line.length > 9 && !line[9].trim().isEmpty()) {
                    Location loc = locationMap.get(line[9].trim());
                    if (loc != null) asset.setLocation(loc);
                }

                boolean isActive = true;
                if (line.length > 11 && !line[11].trim().isEmpty()) {
                    isActive = Boolean.parseBoolean(line[11].trim());
                }
                asset.setIsActive(isActive);

                String qrCode = "AST-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
                asset.setQrCode(qrCode);

                assetsToSave.add(asset);
            }

            if (!assetsToSave.isEmpty()) {
                assetRepository.saveAll(assetsToSave);
                successCount = assetsToSave.size();
            }
        } catch (Exception e) {
            failureCount++;
            errors.add("Failed to parse CSV file: " + e.getMessage());
        }

        return new AssetImportResultDto(successCount, failureCount, errors);
    }

    @Transactional(readOnly = true)
    public void exportAssets(HttpServletResponse response) {
        String tenantId = TenantContext.getCurrentTenant();
        List<Asset> assets = assetRepository.findAll((root, query, cb) -> cb.equal(root.get("tenantId"), tenantId));

        try {
            response.setContentType("text/csv; charset=UTF-8");
            response.setHeader("Content-Disposition", "attachment; filename=\"assets_export.csv\"");

            try (CSVWriter writer = new CSVWriter(new OutputStreamWriter(response.getOutputStream(), "UTF-8"))) {
                String[] header = {
                    "Name", "Category", "Template", "Serial Number", "Model", 
                    "Manufacturer", "Purchase Date", "Value", "Status", "Location", 
                    "QR Code", "IsActive"
                };
                writer.writeNext(header);

            for (Asset a : assets) {
                String[] row = {
                    a.getName() != null ? a.getName() : "",
                    a.getCategory() != null ? a.getCategory().getName() : "",
                    a.getHierarchyTemplate() != null ? a.getHierarchyTemplate().getName() : "",
                    a.getSerialNumber() != null ? a.getSerialNumber() : "",
                    a.getModel() != null ? a.getModel() : "",
                    a.getManufacturer() != null ? a.getManufacturer() : "",
                    a.getPurchaseDate() != null ? a.getPurchaseDate().toString() : "",
                    a.getValue() != null ? a.getValue().toString() : "",
                    a.getStatus() != null ? a.getStatus().name() : "",
                    a.getLocation() != null ? a.getLocation().getName() : "",
                    a.getQrCode() != null ? a.getQrCode() : "",
                    a.getIsActive() != null ? a.getIsActive().toString() : "true"
                };
                writer.writeNext(row);
            }
            } // Close inner try with resources
        } catch (Exception e) {
            throw new RuntimeException("Error writing CSV", e);
        }
    }
}
