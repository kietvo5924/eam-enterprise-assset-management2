package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.services.FileStorageService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/files")
public class FileController {

    @Autowired
    private FileStorageService fileStorageService;

    @Value("${minio.public-url:http://localhost:9000}")
    private String minioPublicUrl;

    @PostMapping("/upload/logo")
    @PreAuthorize("hasAuthority('tenant:update')")
    public ResponseEntity<?> uploadLogo(@RequestParam("file") MultipartFile file) {
        try {
            String objectName = fileStorageService.uploadFile(file, "logos");
            String url = minioPublicUrl + objectName;

            Map<String, String> data = new HashMap<>();
            data.put("url", url);
            return ResponseEntity.ok(ApiResponse.success(data));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(e.getMessage()));
        }
    }
}
