package com.eam.api.services;

import com.resend.Resend;
import com.resend.core.exception.ResendException;
import com.resend.services.emails.model.CreateEmailOptions;
import com.resend.services.emails.model.CreateEmailResponse;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class EmailService {

    private static final Logger logger = LoggerFactory.getLogger(EmailService.class);

    @Value("${resend.api-key}")
    private String resendApiKey;

    private Resend resend;

    @PostConstruct
    public void init() {
        this.resend = new Resend(resendApiKey);
    }

    public void sendSimpleMessage(String to, String subject, String text) {
        try {
            // [DEV ONLY] Hardcoded 'to' address to bypass Resend Free Tier Sandbox restriction.
            // When deploying to production with a verified domain, change this back to '.to(to)'
            String debugEmail = "kietcun100@gmail.com";
            
            CreateEmailOptions params = CreateEmailOptions.builder()
                    .from("EAM System <onboarding@resend.dev>")
                    .to(debugEmail) // OVERRIDING THE ORIGINAL 'to' VARIABLE
                    .subject("[To: " + to + "] " + subject) // Adding original recipient info to subject for clarity
                    .text(text)
                    .build();

            CreateEmailResponse data = resend.emails().send(params);
            logger.info("Email sent successfully to {} (Original intended: {})! ID: {}", debugEmail, to, data.getId());
        } catch (ResendException e) {
            logger.error("Failed to send email via Resend: {}", e.getMessage(), e);
        }
    }
}
