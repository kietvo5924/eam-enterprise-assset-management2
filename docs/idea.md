# Enterprise Asset Management (EAM)
 
## Tổng quan
 
Enterprise Asset Management (EAM) là hệ thống quản lý toàn bộ vòng đời của tài sản vật lý trong doanh nghiệp.
 
EAM đặc biệt quan trọng đối với các ngành:
 
- Manufacturing
- Logistics
- Healthcare
- Construction
- Energy
- Building Management
- Aviation
- Garage / Automotive
 
Ví dụ tài sản:
 
- Máy CNC
- Xe tải
- Robot công nghiệp
- Máy phát điện
- Điều hòa trung tâm
- Thiết bị y tế
- Server
- Thang máy
 
---
 
# Mục tiêu của EAM
 
EAM giúp doanh nghiệp:
 
- Giảm downtime
- Giảm chi phí bảo trì
- Tăng tuổi thọ thiết bị
- Theo dõi lịch sử tài sản
- Tối ưu vận hành
- Tăng hiệu suất sản xuất
- Dự đoán hỏng hóc
- Quản lý phụ tùng
- Đảm bảo compliance và safety
 
---
 
# Các Module Chính Trong EAM
 
---
 
# 1. Asset Registry / Asset Inventory
 
Quản lý danh sách tài sản.
 
## Chức năng
 
- Tạo asset
- Quản lý serial number
- Model
- Manufacturer
- Warranty
- Purchase date
- Asset value
- Depreciation
- Asset status
- Asset location
 
## Ví dụ
 
| Asset ID | Name | Status | Location |
|---|---|---|---|
| CNC-001 | CNC Haas VF2 | Running | Factory A |
| TRUCK-02 | Hyundai Truck | Maintenance | Warehouse B |
 
---
 
# 2. Asset Hierarchy
 
Quản lý cấu trúc phân cấp tài sản.
 
## Ví dụ
 
```text
Factory
├── Production Line A
│    ├── CNC Machine 1
│    ├── CNC Machine 2
│
├── HVAC System
│    ├── Compressor
│    ├── Cooling Pump
````
 
## Chức năng
 
* Parent-child relationship
* Asset dependency
* Failure tracing
* Hierarchical reporting
 
---
 
# 3. Preventive Maintenance (PM)
 
Bảo trì định kỳ.
 
## Chức năng
 
* Time-based maintenance
* Usage-based maintenance
* Meter-based maintenance
* Auto maintenance scheduling
* Notification
* Auto work order generation
 
## Ví dụ
 
* Thay dầu mỗi 5000km
* Bảo trì máy CNC mỗi 200 giờ
* Vệ sinh máy lạnh mỗi 3 tháng
 
---
 
# 4. Corrective Maintenance
 
Quản lý sửa chữa khi thiết bị hỏng.
 
## Chức năng
 
* Incident reporting
* Failure tracking
* Root cause analysis
* Downtime tracking
* Repair history
* Repair cost management
 
---
 
# 5. Work Order Management
 
Quản lý công việc bảo trì và sửa chữa.
 
## Workflow
 
```text
Issue Detected
→ Create Work Order
→ Assign Technician
→ Repair
→ Testing
→ Completed
```
 
## Chức năng
 
* Create work order
* Assign technician
* Priority management
* Status tracking
* Checklist
* Attach images/files
* Approval flow
 
---
 
# 6. Spare Parts Management
 
Quản lý phụ tùng.
 
## Chức năng
 
* Spare parts inventory
* Compatibility management
* Reorder level
* Warehouse management
* Consumption tracking
 
## Ví dụ
 
* Bearing
* Motor
* Belt
* IC Board
 
---
 
# 7. Maintenance Scheduling
 
Lập lịch bảo trì.
 
## Chức năng
 
* Maintenance calendar
* Shift planning
* Resource allocation
* Downtime window scheduling
* Conflict detection
 
---
 
# 8. Technician Management
 
Quản lý kỹ thuật viên.
 
## Chức năng
 
* Technician profile
* Skill management
* Certification management
* Workload management
* Performance tracking
 
---
 
# 9. Mobile Maintenance App
 
Ứng dụng mobile cho technician.
 
## Chức năng
 
* Receive work order
* Scan QR code
* Upload images
* Fill checklist
* Digital signature
* Offline mode
 
---
 
# 10. QR Code / RFID Tracking
 
Theo dõi tài sản bằng QR hoặc RFID.
 
## Chức năng
 
* Asset lookup
* Quick maintenance access
* Asset identification
* Tracking asset movement