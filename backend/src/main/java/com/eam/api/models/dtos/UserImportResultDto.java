package com.eam.api.models.dtos;

import java.util.List;

public class UserImportResultDto {
    private int successCount;
    private int failureCount;
    private List<String> errors;

    public UserImportResultDto() {}

    public UserImportResultDto(int successCount, int failureCount, List<String> errors) {
        this.successCount = successCount;
        this.failureCount = failureCount;
        this.errors = errors;
    }

    public int getSuccessCount() { return successCount; }
    public void setSuccessCount(int successCount) { this.successCount = successCount; }

    public int getFailureCount() { return failureCount; }
    public void setFailureCount(int failureCount) { this.failureCount = failureCount; }

    public List<String> getErrors() { return errors; }
    public void setErrors(List<String> errors) { this.errors = errors; }
}
