package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.core.security.JwtUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    @Autowired
    private JwtUtils jwtUtils;

    @Autowired
    private com.eam.api.repositories.TenantRepository tenantRepository;
    
    @Autowired
    private org.springframework.security.crypto.password.PasswordEncoder passwordEncoder;

    @Autowired
    private com.eam.api.repositories.UserRepository userRepository;

    @Autowired
    private com.eam.api.services.EmailService emailService;

    @PostMapping("/login")
    public ApiResponse<Map<String, String>> login(@RequestBody Map<String, String> loginRequest) {
        String username = loginRequest.get("username");
        String password = loginRequest.get("password");
        
        for (com.eam.api.models.entities.Tenant t : tenantRepository.findAll()) {
            com.eam.api.core.tenant.TenantContext.setCurrentTenant(t.getId().toString());
            try {
                java.util.Optional<com.eam.api.models.entities.User> optUser = userRepository.findByUsernameAndTenantId(username, t.getId().toString());
                if (optUser.isPresent()) {
                    com.eam.api.models.entities.User user = optUser.get();
                    if (passwordEncoder.matches(password, user.getPasswordHash())) {
                        if ("INACTIVE".equals(t.getStatus())) {
                            return ApiResponse.error("Organization account is currently locked or inactive");
                        }
                        if (user.getStatus() == com.eam.api.models.entities.UserStatus.INACTIVE) {
                            return ApiResponse.error("User account is inactive");
                        }
                        String token = jwtUtils.generateJwtToken(username, t.getId().toString());
                        String rolesStr = user.getRoles().stream().map(com.eam.api.models.entities.Role::getName).reduce((a, b) -> a + "," + b).orElse("");
                        java.util.Set<String> perms = new java.util.HashSet<>();
                        user.getRoles().forEach(r -> r.getPermissions().forEach(p -> perms.add(p.getId())));
                        String permsStr = String.join(",", perms);
                        return ApiResponse.success(Map.of("token", token, "tenantId", t.getId().toString(), "roles", rolesStr, "permissions", permsStr));
                    } else {
                        return ApiResponse.error("Incorrect password");
                    }
                }
            } finally {
                com.eam.api.core.tenant.TenantContext.clear();
            }
        }
        
        return ApiResponse.error("Account does not exist");
    }

    @PostMapping("/change-password")
    public ApiResponse<Void> changePassword(@RequestBody Map<String, String> request) {
        String oldPassword = request.get("oldPassword");
        String newPassword = request.get("newPassword");
        
        org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) {
            return ApiResponse.error("Not authenticated");
        }
        
        String username = auth.getName();
        String tenantId = com.eam.api.core.tenant.TenantContext.getCurrentTenant();
        
        java.util.Optional<com.eam.api.models.entities.User> optUser = userRepository.findByUsernameAndTenantId(username, tenantId);
        if (optUser.isPresent()) {
            com.eam.api.models.entities.User user = optUser.get();
            if (!passwordEncoder.matches(oldPassword, user.getPasswordHash())) {
                return ApiResponse.error("Incorrect old password");
            }
            user.setPasswordHash(passwordEncoder.encode(newPassword));
            userRepository.save(user);
            return ApiResponse.success(null);
        }
        return ApiResponse.error("User not found");
    }

    @PostMapping("/forgot-password")
    public ApiResponse<Void> forgotPassword(@RequestBody Map<String, String> request) {
        String email = request.get("email");
        java.util.List<com.eam.api.models.entities.User> users = userRepository.findAllByEmail(email);
        
        if (!users.isEmpty()) {
            // Usually, there should be one user per email across tenants, or we just pick the first active one.
            com.eam.api.models.entities.User user = users.get(0);
            
            // Generate a 6-digit code
            String code = String.format("%06d", new java.util.Random().nextInt(999999));
            user.setResetToken(code);
            user.setResetTokenExpiry(java.time.ZonedDateTime.now().plusMinutes(15));
            userRepository.save(user);
            
            try {
                emailService.sendSimpleMessage(email, "Password Reset Code", "Your password reset code is: " + code + "\nIt will expire in 15 minutes.");
                return ApiResponse.success(null);
            } catch (Exception e) {
                // If it fails, maybe the app password is wrong or expired
                // Rollback the token to be safe
                user.setResetToken(null);
                user.setResetTokenExpiry(null);
                userRepository.save(user);
                return ApiResponse.error("Failed to send email. The email API key might be expired. " + e.getMessage());
            }
        }
        
        // For security, do not reveal if the email exists
        return ApiResponse.success(null);
    }

    @PostMapping("/reset-password")
    public ApiResponse<Void> resetPassword(@RequestBody Map<String, String> request) {
        String code = request.get("code");
        String newPassword = request.get("newPassword");
        
        java.util.Optional<com.eam.api.models.entities.User> optUser = userRepository.findByResetToken(code);
        if (optUser.isPresent()) {
            com.eam.api.models.entities.User user = optUser.get();
            if (user.getResetTokenExpiry().isAfter(java.time.ZonedDateTime.now())) {
                user.setPasswordHash(passwordEncoder.encode(newPassword));
                user.setResetToken(null);
                user.setResetTokenExpiry(null);
                userRepository.save(user);
                return ApiResponse.success(null);
            } else {
                return ApiResponse.error("Reset code has expired");
            }
        }
        return ApiResponse.error("Invalid reset code");
    }
}
