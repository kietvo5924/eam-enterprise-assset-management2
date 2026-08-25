package com.eam.api.controllers;

import com.eam.api.core.payload.ApiResponse;
import com.eam.api.models.dtos.UserCreateRequest;
import com.eam.api.models.dtos.UserDto;
import com.eam.api.models.dtos.UserUpdateRequest;
import com.eam.api.models.dtos.UserInviteRequest;
import com.eam.api.models.dtos.UserImportResultDto;
import com.eam.api.services.UserService;
import com.eam.api.services.UserImportService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    @Autowired
    private UserService userService;

    @Autowired
    private UserImportService userImportService;

    @GetMapping
    @PreAuthorize("hasAuthority('user:read')")
    public ApiResponse<Page<UserDto>> getUsers(
            @RequestParam(required = false) String roleName,
            @RequestParam(required = false) String permissionId,
            Pageable pageable) {
        Page<UserDto> users = userService.getUsers(roleName, permissionId, pageable);
        return ApiResponse.success(users);
    }

    @PostMapping
    @PreAuthorize("hasAuthority('user:create')")
    public ApiResponse<UserDto> createUser(@Valid @RequestBody UserCreateRequest request) {
        UserDto user = userService.createUser(request);
        return ApiResponse.success(user);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAuthority('user:update')")
    public ApiResponse<UserDto> updateUser(@PathVariable UUID id, @Valid @RequestBody UserUpdateRequest request) {
        UserDto user = userService.updateUser(id, request);
        return ApiResponse.success(user);
    }

    @PutMapping("/{id}/disable")
    @PreAuthorize("hasAuthority('user:update')")
    public ApiResponse<Void> disableUser(@PathVariable UUID id) {
        userService.disableUser(id);
        return ApiResponse.success(null);
    }

    @PutMapping("/{id}/enable")
    @PreAuthorize("hasAuthority('user:update')")
    public ApiResponse<Void> enableUser(@PathVariable UUID id) {
        userService.enableUser(id);
        return ApiResponse.success(null);
    }

    @PostMapping("/invite")
    @PreAuthorize("hasAuthority('user:create')")
    public ApiResponse<Void> inviteUser(@Valid @RequestBody UserInviteRequest request) {
        userService.inviteUser(request);
        return ApiResponse.success(null);
    }

    @PostMapping("/import")
    @PreAuthorize("hasAuthority('user:create')")
    public ApiResponse<UserImportResultDto> importUsers(@RequestParam("file") MultipartFile file) {
        UserImportResultDto result = userImportService.importUsers(file);
        return ApiResponse.success(result);
    }
}
