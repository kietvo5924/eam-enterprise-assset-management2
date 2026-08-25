import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/work_order.dart';
import '../services/work_order_service.dart';
import '../../../core/database/app_database.dart';
import '../../../core/database/database_mapper.dart';
class WorkOrderProvider extends ChangeNotifier {
  final WorkOrderService _service = WorkOrderService();

  List<WorkOrder> _homeWorkOrders = [];
  List<WorkOrder> get homeWorkOrders => _homeWorkOrders;

  List<WorkOrder> _myWorkOrders = [];
  List<WorkOrder> get myWorkOrders => _myWorkOrders;

  bool _isLoadingHome = false;
  bool get isLoadingHome => _isLoadingHome;

  bool _isLoadingList = false;
  bool get isLoadingList => _isLoadingList;

  StreamSubscription<List<WorkOrderEntity>>? _homeSub;

  @override
  void dispose() {
    _homeSub?.cancel();
    super.dispose();
  }

  Future<void> fetchHomeWorkOrders() async {
    _isLoadingHome = true;
    // Removed notifyListeners() to prevent blocking UI during background sync

    try {
      final prefs = await SharedPreferences.getInstance();
      final myUsername = prefs.getString('username') ?? '';
      final tenantId = prefs.getString('tenantId') ?? '';
      
      // 1. Listen to Local DB Stream for real-time offline-first updates
      if (tenantId.isNotEmpty && myUsername.isNotEmpty) {
        _homeSub?.cancel();
        _homeSub = AppDatabase.instance.workOrderDao.watchMyWorkOrders(myUsername, tenantId).listen((entities) {
          final mapped = entities.map((e) => DatabaseMapper.fromWorkOrderEntity(e)).toList();
          _homeWorkOrders = mapped.where((wo) => wo.status != 'COMPLETED' && wo.status != 'CANCELED').toList();
          notifyListeners();
        });
      }

      // 2. Trigger API fetch to update local DB
      await _service.getMobileHomeWorkOrders();
      
    } catch (e) {
      debugPrint('Error fetching home work orders: $e');
    } finally {
      _isLoadingHome = false;
      notifyListeners();
    }
  }

  int _currentPage = 0;
  bool _hasMore = true;
  bool get hasMore => _hasMore;

  bool _isFetchingMore = false;
  bool get isFetchingMore => _isFetchingMore;

  Future<void> fetchMyWorkOrders({bool refresh = false}) async {
    if (refresh) {
      _currentPage = 0;
      _hasMore = true;
      _isLoadingList = true;
      _myWorkOrders.clear();
      notifyListeners();
    } else {
      if (!_hasMore || _isFetchingMore || _isLoadingList) return;
      _isFetchingMore = true;
      notifyListeners();
    }

    try {
      final result = await _service.getMyWorkOrders(page: _currentPage, size: 20);
      final newItems = result['data'] as List<WorkOrder>;
      final isLast = result['last'] as bool;

      if (refresh) {
        _myWorkOrders = newItems;
      } else {
        _myWorkOrders.addAll(newItems);
      }

      _hasMore = !isLast;
      if (_hasMore) {
        _currentPage++;
      }
    } catch (e) {
      debugPrint('Error fetching my work orders: $e');
    } finally {
      _isLoadingList = false;
      _isFetchingMore = false;
      notifyListeners();
    }
  }
}
