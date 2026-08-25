package com.eam.api.models.dtos;

public class MaintenanceKpiDto {
    private long totalPlans;
    private long upcomingIn7Days;
    private long missedPms;
    private double complianceRate;

    public MaintenanceKpiDto() {}

    public long getTotalPlans() {
        return totalPlans;
    }

    public void setTotalPlans(long totalPlans) {
        this.totalPlans = totalPlans;
    }

    public long getUpcomingIn7Days() {
        return upcomingIn7Days;
    }

    public void setUpcomingIn7Days(long upcomingIn7Days) {
        this.upcomingIn7Days = upcomingIn7Days;
    }

    public long getMissedPms() {
        return missedPms;
    }

    public void setMissedPms(long missedPms) {
        this.missedPms = missedPms;
    }

    public double getComplianceRate() {
        return complianceRate;
    }

    public void setComplianceRate(double complianceRate) {
        this.complianceRate = complianceRate;
    }
}
