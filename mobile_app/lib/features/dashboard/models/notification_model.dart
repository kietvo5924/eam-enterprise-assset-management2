class NotificationItem {
  final String id;
  final String title;
  final String message;
  final String category;
  final String severity;
  final bool isRead;
  final DateTime? readAt;
  final bool isActionable;
  final String actionStatus;
  final DateTime? actionResolvedAt;
  final String? link;
  final DateTime createdAt;
  final Map<String, dynamic>? sender;

  NotificationItem({
    required this.id,
    required this.title,
    required this.message,
    required this.category,
    required this.severity,
    required this.isRead,
    this.readAt,
    required this.isActionable,
    required this.actionStatus,
    this.actionResolvedAt,
    this.link,
    required this.createdAt,
    this.sender,
  });

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    DateTime parseDate(dynamic val) {
      if (val == null) return DateTime.now();
      try {
        return DateTime.parse(val.toString());
      } catch (_) {
        return DateTime.now();
      }
    }

    return NotificationItem(
      id: json['id']?.toString() ?? '',
      title: json['title'] ?? 'Thông báo',
      message: json['message'] ?? '',
      category: (json['category'] ?? 'SYSTEM').toString().toUpperCase(),
      severity: (json['severity'] ?? 'INFO').toString().toUpperCase(),
      isRead: json['is_read'] == true || json['isRead'] == true,
      readAt: json['read_at'] != null ? parseDate(json['read_at']) : (json['readAt'] != null ? parseDate(json['readAt']) : null),
      isActionable: json['is_actionable'] == true || json['isActionable'] == true,
      actionStatus: (json['action_status'] ?? json['actionStatus'] ?? 'NONE').toString().toUpperCase(),
      actionResolvedAt: json['action_resolved_at'] != null
          ? parseDate(json['action_resolved_at'])
          : (json['actionResolvedAt'] != null ? parseDate(json['actionResolvedAt']) : null),
      link: json['link']?.toString(),
      createdAt: parseDate(json['created_at'] ?? json['createdAt']),
      sender: json['sender'] is Map<String, dynamic> ? json['sender'] as Map<String, dynamic> : null,
    );
  }

  NotificationItem copyWith({
    bool? isRead,
    String? actionStatus,
    DateTime? actionResolvedAt,
  }) {
    return NotificationItem(
      id: id,
      title: title,
      message: message,
      category: category,
      severity: severity,
      isRead: isRead ?? this.isRead,
      readAt: readAt,
      isActionable: isActionable,
      actionStatus: actionStatus ?? this.actionStatus,
      actionResolvedAt: actionResolvedAt ?? this.actionResolvedAt,
      link: link,
      createdAt: createdAt,
      sender: sender,
    );
  }
}
