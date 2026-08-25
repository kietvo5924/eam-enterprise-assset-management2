# Sprint Change Proposal - ERP-Standard MVP Course Correction

**Project:** eam-enterprise-assset-management  
**Date:** 2026-05-20  
**Trigger:** User clarified the first release should follow ERP-standard expectations, not a reduced Lean MVP.

## 1. Issue Summary

The previous Lean MVP adjustment reduced scope to "usable first". The product direction is now corrected: the MVP should be a serious ERP-style business system with the expected operational foundations included from the first implementation plan.

## 2. Recommended Direction

**Selected path:** Direct Adjustment back to ERP-standard MVP.

Keep all core PRD functional requirements inside MVP unless explicitly marked post-MVP in the original scope. Tighten stories so they are implementation-ready instead of deferring important platform behavior.

## 3. ERP-Standard MVP Scope

The first implementation should include:

- Configurable RBAC role/permission management.
- Manual user creation plus invite/import workflow.
- Tenant isolation and audit trail as first-class requirements.
- Asset CRUD, hierarchy, QR generation, search/filter, maintenance history.
- Work Order lifecycle with assignment, reassign, status transitions, deadline, checklist, notes, photo upload validation.
- Preventive Maintenance with time-based, usage-based, and meter-based triggers.
- Notification engine covering Web realtime and Mobile push, with unread state.
- Mobile offline cache, sync retry, and explicit conflict/idempotency handling.
- Basic CI/test quality gate, migration safety, and backup/restore guardrails.
- Baseline accessibility aligned with UX target.

## 4. Artifact Changes Needed

### PRD

Remove the Lean MVP clarification that deferred ERP-standard capabilities.

### Epics

Restore all FRs to MVP coverage and add missing story-level acceptance criteria:

- FR6/FR7 back in Epic 1.
- FR34 back in Epic 5.
- Epic 6 returns to Real-time Communications.
- Add foundation hardening story for backup/restore/migration safety.
- Add offline sync contract/conflict handling story.

### Architecture

Replace Lean MVP Architecture Note with ERP-standard implementation contracts for:

- Notification delivery via Kafka + WebSocket + FCM.
- Offline sync idempotency and conflict handling.
- Tenant theme delivery.
- Operational safeguards.

## 5. Scope Classification

**Moderate**

This is a backlog/artifact correction, not a product reset.

## 6. Approval

**Status:** Approved by user direction: "tôi muốn chuẩn ERP".
