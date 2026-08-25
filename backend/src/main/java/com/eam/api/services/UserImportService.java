package com.eam.api.services;

import com.eam.api.core.tenant.TenantContext;
import com.eam.api.models.dtos.UserImportResultDto;
import com.eam.api.models.entities.Role;
import com.eam.api.models.entities.User;
import com.eam.api.models.entities.UserStatus;
import com.eam.api.repositories.RoleRepository;
import com.eam.api.repositories.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.*;

@Service
public class UserImportService {

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private RoleRepository roleRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Transactional
    public UserImportResultDto importUsers(MultipartFile file) {
        String tenantId = TenantContext.getCurrentTenant();
        int successCount = 0;
        int failureCount = 0;
        List<String> errors = new ArrayList<>();

        List<User> existingUsers = userRepository.findByTenantId(tenantId);
        Set<String> existingEmails = new HashSet<>();
        Set<String> existingUsernames = new HashSet<>();
        for (User u : existingUsers) {
            if (u.getEmail() != null)
                existingEmails.add(u.getEmail());
            if (u.getUsername() != null)
                existingUsernames.add(u.getUsername());
        }

        List<Role> allRoles = roleRepository.findByTenantId(tenantId); // assuming this exists, if not we fall back
        Map<String, Role> roleMap = new HashMap<>();
        for (Role r : allRoles) {
            roleMap.put(r.getName(), r);
        }

        List<User> usersToSave = new ArrayList<>();

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(file.getInputStream()))) {

            String headerLine = reader.readLine(); // Skip header
            if (headerLine == null) {
                errors.add("File is empty");
                return new UserImportResultDto(0, 1, errors);
            }

            String lineText;
            int lineNumber = 1;
            while ((lineText = reader.readLine()) != null) {
                lineNumber++;
                if (lineText.trim().isEmpty())
                    continue;

                // Support both comma and semicolon separators (common in Excel exports)
                String[] line = lineText.split("[,;]");

                if (line.length < 3) {
                    failureCount++;
                    errors.add("Line " + lineNumber + ": Missing required columns (username, email, password)");
                    continue;
                }

                String username = line[0].trim();
                String email = line[1].trim();
                String password = line[2].trim();
                String roleNamesRaw = line.length > 3 ? line[3] : "";

                if (existingEmails.contains(email)) {
                    failureCount++;
                    errors.add("Line " + lineNumber + ": Email " + email + " already exists");
                    continue;
                }

                if (existingUsernames.contains(username)) {
                    failureCount++;
                    errors.add("Line " + lineNumber + ": Username " + username + " already exists");
                    continue;
                }

                User user = new User();
                user.setTenantId(tenantId);
                user.setUsername(username);
                user.setEmail(email);
                user.setPasswordHash(passwordEncoder.encode(password));
                user.setStatus(UserStatus.ACTIVE);

                Set<Role> roles = new HashSet<>();
                if (!roleNamesRaw.isEmpty()) {
                    String[] names = roleNamesRaw.split(",");
                    for (String name : names) {
                        Role r = roleMap.get(name.trim());
                        if (r != null) {
                            roles.add(r);
                        } else {
                            // If role not pre-fetched, fallback to query
                            roleRepository.findByNameAndTenantId(name.trim(), tenantId).ifPresent(roles::add);
                        }
                    }
                }
                user.setRoles(roles);

                usersToSave.add(user);
                existingEmails.add(email);
                existingUsernames.add(username);
            }

            if (!usersToSave.isEmpty()) {
                userRepository.saveAll(usersToSave);
                successCount = usersToSave.size();
            }

        } catch (Exception e) {
            failureCount++;
            errors.add("Failed to parse CSV file: " + e.getMessage());
        }

        return new UserImportResultDto(successCount, failureCount, errors);
    }
}
