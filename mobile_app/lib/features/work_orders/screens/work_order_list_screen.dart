import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/providers/user_provider.dart';
import '../providers/work_order_provider.dart';
import '../models/work_order.dart';

class WorkOrderListScreen extends StatefulWidget {
  const WorkOrderListScreen({super.key});

  @override
  State<WorkOrderListScreen> createState() => _WorkOrderListScreenState();
}

class _WorkOrderListScreenState extends State<WorkOrderListScreen> {
  String _searchQuery = '';
  String _selectedStatus = 'ALL';
  
  final List<Map<String, String>> _statusFilters = [
    {'value': 'ALL', 'label': 'Tất cả'},
    {'value': 'ASSIGNED', 'label': 'Được giao'},
    {'value': 'IN_PROGRESS', 'label': 'Đang làm'},
    {'value': 'COMPLETED', 'label': 'Hoàn thành'},
    {'value': 'CANCELED', 'label': 'Đã hủy'},
  ];

  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<WorkOrderProvider>().fetchMyWorkOrders(refresh: true);
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      final provider = context.read<WorkOrderProvider>();
      if (provider.hasMore && !provider.isFetchingMore && !provider.isLoadingList) {
        provider.fetchMyWorkOrders();
      }
    }
  }

  List<WorkOrder> _getFilteredWorkOrders(List<WorkOrder> workOrders) {
    return workOrders.where((wo) {
      final matchesSearch = wo.title.toLowerCase().contains(_searchQuery.toLowerCase()) || 
                            (wo.assetName?.toLowerCase().contains(_searchQuery.toLowerCase()) ?? false) ||
                            wo.id.toLowerCase().contains(_searchQuery.toLowerCase());
      final matchesStatus = _selectedStatus == 'ALL' || wo.status == _selectedStatus;
      return matchesSearch && matchesStatus;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final userProvider = context.watch<UserProvider>();
    final woProvider = context.watch<WorkOrderProvider>();
    
    final bool _canCreate = userProvider.canCreateWorkOrder;
    final bool _isLoading = woProvider.isLoadingList;
    final List<WorkOrder> _filteredWorkOrders = _getFilteredWorkOrders(woProvider.myWorkOrders);

    return Scaffold(
      backgroundColor: AppTheme.neutral50,
      appBar: AppBar(
        title: const Text('Danh sách Công việc', style: TextStyle(color: AppTheme.neutral900, fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: Colors.white,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppTheme.neutral900),
      ),
      floatingActionButton: _canCreate
          ? FloatingActionButton(
              onPressed: () async {
                final result = await context.push('/create-work-order');
                if (result == true && context.mounted) {
                  context.read<WorkOrderProvider>().fetchMyWorkOrders(refresh: true);
                }
              },
              backgroundColor: AppTheme.primaryColor,
              child: Icon(PhosphorIcons.plus(), color: Colors.white),
            )
          : null,
      body: _isLoading  
        ? const Center(child: CircularProgressIndicator())
        : Column(
            children: [
              // Search & Filter
              Container(
                padding: const EdgeInsets.all(16),
                decoration: const BoxDecoration(
                  color: Colors.white,
                  border: Border(bottom: BorderSide(color: AppTheme.neutral200)),
                ),
                child: Column(
                  children: [
                    // Search bar
                    Container(
                      decoration: BoxDecoration(
                        color: AppTheme.neutral100,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: TextField(
                        onChanged: (val) {
                          setState(() { _searchQuery = val; });
                        },
                        decoration: InputDecoration(
                          hintText: 'Tìm kiếm công việc, thiết bị...',
                          hintStyle: const TextStyle(color: AppTheme.neutral400, fontSize: 14),
                          prefixIcon: Icon(PhosphorIcons.magnifyingGlass(), color: AppTheme.neutral400),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    // Status filters
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: _statusFilters.map((filter) {
                          final isSelected = _selectedStatus == filter['value'];
                          return Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: FilterChip(
                              label: Text(filter['label']!),
                              labelStyle: TextStyle(
                                color: isSelected ? Colors.white : AppTheme.neutral600,
                                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                fontSize: 13,
                              ),
                              backgroundColor: AppTheme.neutral100,
                              selectedColor: AppTheme.primaryColor,
                              selected: isSelected,
                              showCheckmark: false,
                              side: BorderSide.none,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                              onSelected: (selected) {
                                setState(() {
                                  _selectedStatus = filter['value']!;
                                });
                              },
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                  ],
                ),
              ),
              // List
              Expanded(
                child: _filteredWorkOrders.isEmpty
                  ? const Center(
                      child: Text('Không tìm thấy công việc phù hợp', style: TextStyle(color: AppTheme.neutral500))
                    )
                  : RefreshIndicator(
                      onRefresh: () async {
                        await context.read<WorkOrderProvider>().fetchMyWorkOrders(refresh: true);
                      },
                      child: ListView.builder(
                        controller: _scrollController,
                        physics: const AlwaysScrollableScrollPhysics(),
                        padding: const EdgeInsets.only(left: 16, right: 16, top: 16, bottom: 80),
                        itemCount: _filteredWorkOrders.length + (woProvider.isFetchingMore ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index == _filteredWorkOrders.length) {
                            return const Padding(
                              padding: EdgeInsets.symmetric(vertical: 16),
                              child: Center(child: CircularProgressIndicator()),
                            );
                          }
                          final wo = _filteredWorkOrders[index];
                          final statusUI = wo.getStatusUI();
                          return _buildWOCard(
                            context: context,
                            status: statusUI['label'],
                            statusColor: statusUI['color'],
                            statusBgColor: statusUI['bgColor'],
                            statusTextColor: statusUI['textColor'],
                            id: wo.id,
                            code: 'WO-${wo.id.substring(0,4)}',
                            title: wo.title,
                            location: wo.assetName ?? 'Chưa gắn thiết bị',
                            timeOrInfo: wo.getFormattedTime(),
                            timeOrInfoColor: wo.status == 'IN_PROGRESS' ? const Color(0xFFea580c) : AppTheme.neutral400,
                          );
                        },
                      ),
                    ),
              ),
            ],
          ),
    );
  }

  Widget _buildWOCard({
    required BuildContext context,
    required String status,
    required Color statusColor,
    required Color statusBgColor,
    required Color statusTextColor,
    required String id,
    required String code,
    required String title,
    required String location,
    required String timeOrInfo,
    required Color timeOrInfoColor,
  }) {
    return GestureDetector(
      onTap: () async {
        await context.push('/work-order-detail/$id', extra: code);
        if (context.mounted) {
          context.read<WorkOrderProvider>().fetchMyWorkOrders(refresh: true);
        }
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: AppTheme.neutral900.withValues(alpha: 0.04),
              blurRadius: 12,
              offset: const Offset(0, 4),
            )
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(color: statusBgColor, borderRadius: BorderRadius.circular(6)),
                  child: Row(
                    children: [
                      Container(width: 6, height: 6, decoration: BoxDecoration(color: statusColor, shape: BoxShape.circle)),
                      const SizedBox(width: 4),
                      Text(status.toUpperCase(), style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: statusTextColor, letterSpacing: 0.5)),
                    ],
                  ),
                ),
                Text(code, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.neutral400)),
              ],
            ),
            const SizedBox(height: 12),
            Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.neutral900)),
            const SizedBox(height: 4),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(location, style: const TextStyle(fontSize: 12, color: AppTheme.neutral500)),
                Text(timeOrInfo, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: timeOrInfoColor)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
