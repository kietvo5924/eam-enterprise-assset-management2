package com.eam.api.core.security;

import com.eam.api.core.tenant.TenantContext;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    @Autowired
    private JwtUtils jwtUtils;

    @Autowired
    private com.eam.api.repositories.UserRepository userRepository;

    @Autowired
    private com.eam.api.repositories.TenantRepository tenantRepository;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        try {
            String jwt = parseJwt(request);
            if (jwt != null && jwtUtils.validateJwtToken(jwt)) {
                String username = jwtUtils.getUserNameFromJwtToken(jwt);
                String tenantId = jwtUtils.getTenantIdFromJwtToken(jwt);

                // Set tenant context
                if (tenantId != null) {
                    TenantContext.setCurrentTenant(tenantId);
                }

                // In a real app, load UserDetails from DB
                java.util.List<org.springframework.security.core.GrantedAuthority> authorities = new java.util.ArrayList<>();

                if (tenantId != null && username != null) {
                    java.util.Optional<com.eam.api.models.entities.Tenant> tenantOpt = tenantRepository
                            .findById(java.util.UUID.fromString(tenantId));
                    if (tenantOpt.isPresent() && "INACTIVE".equals(tenantOpt.get().getStatus())) {
                        return; // Block access completely for inactive tenants
                    }

                    userRepository.findByUsernameAndTenantId(username, tenantId).ifPresent(user -> {
                        if (user.getStatus() == com.eam.api.models.entities.UserStatus.INACTIVE) {
                            return;
                        }
                        user.getRoles().forEach(role -> {
                            authorities.add(new org.springframework.security.core.authority.SimpleGrantedAuthority(
                                    "ROLE_" + role.getName()));
                            role.getPermissions().forEach(permission -> {
                                authorities.add(new org.springframework.security.core.authority.SimpleGrantedAuthority(
                                        permission.getId()));
                            });
                        });

                        CustomUserDetails userDetails = new CustomUserDetails(user.getId(), user.getUsername(),
                                user.getPasswordHash(), authorities);
                        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                                userDetails, null, authorities);
                        authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));

                        SecurityContextHolder.getContext().setAuthentication(authentication);
                    });
                }
            }
        } catch (Exception e) {
            // Cannot set user authentication
        }

        try {
            filterChain.doFilter(request, response);
        } finally {
            // Always clear context to prevent memory leaks and cross-request contamination
            TenantContext.clear();
        }
    }

    private String parseJwt(HttpServletRequest request) {
        String headerAuth = request.getHeader("Authorization");

        if (StringUtils.hasText(headerAuth) && headerAuth.startsWith("Bearer ")) {
            return headerAuth.substring(7);
        }

        return null;
    }
}
