import 'package:flutter/material.dart';
import 'package:mobile_app/services/api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic> _stats = {};
  List<dynamic> _todayScans = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
    });

    final stats = await ApiService().getDashboardStats();
    final scans = await ApiService().getTodayAttendance();

    if (mounted) {
      setState(() {
        _stats = stats;
        _todayScans = scans;
        _isLoading = false;
      });
    }
  }

  Widget _buildKpiCard({
    required String title,
    required String value,
    required IconData icon,
    required Color color,
    required String metaLabel,
    required String metaBadge,
    bool hasPulsePip = false,
    double? progressPercent,
  }) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : const Color(0xFFE2E8F0),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: Stack(
          children: [
            // Top Accent Color Stripe
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Container(
                height: 4,
                color: color,
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 16, 14, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Label + Icon Bubble Row
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Row(
                          children: [
                            if (hasPulsePip) ...[
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  color: color,
                                  shape: BoxShape.circle,
                                  boxShadow: [
                                    BoxShadow(
                                      color: color.withValues(alpha: 0.6),
                                      blurRadius: 6,
                                      spreadRadius: 1,
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 5),
                            ],
                            Flexible(
                              child: Text(
                                title.toUpperCase(),
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: 0.4,
                                  color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        width: 34,
                        height: 34,
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(icon, color: color, size: 18),
                      ),
                    ],
                  ),

                  // Large Prominent Number Value
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Text(
                      value,
                      style: TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.5,
                        fontFamily: 'monospace',
                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                      ),
                    ),
                  ),

                  // Optional Progress Bar
                  if (progressPercent != null)
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: (progressPercent / 100.0).clamp(0.0, 1.0),
                        backgroundColor: isDark
                            ? Colors.white.withValues(alpha: 0.1)
                            : const Color(0xFFE2E8F0),
                        valueColor: AlwaysStoppedAnimation<Color>(color),
                        minHeight: 4,
                      ),
                    ),

                  // Telemetry Footer
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Flexible(
                        child: Text(
                          metaLabel,
                          style: TextStyle(
                            fontSize: 9.5,
                            fontWeight: FontWeight.w600,
                            color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          metaBadge,
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.bold,
                            color: color,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final totalStudents = _stats['total_students']?.toString() ?? "0";
    final presentToday = _stats['present_today']?.toString() ?? "0";
    final absentToday = _stats['absent_today']?.toString() ?? "0";
    final rate = _stats['attendance_rate']?.toString() ?? "0";

    return Scaffold(
      appBar: AppBar(
        title: const Text("ERP Analytics Dashboard"),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadData,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // KPI Grid (Enlarged Prominent Cards with Telemetry)
                    GridView.count(
                      crossAxisCount: 2,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      childAspectRatio: 1.12,
                      children: [
                        _buildKpiCard(
                          title: "Enrolled",
                          value: totalStudents,
                          icon: Icons.people_alt_rounded,
                          color: const Color(0xFF0284C7),
                          metaLabel: "Active Roster",
                          metaBadge: "100% Synced",
                        ),
                        _buildKpiCard(
                          title: "Present",
                          value: presentToday,
                          icon: Icons.check_circle_rounded,
                          color: const Color(0xFF0D9488),
                          metaLabel: "On Campus",
                          metaBadge: "$presentToday Verified",
                          hasPulsePip: true,
                        ),
                        _buildKpiCard(
                          title: "Absent",
                          value: absentToday,
                          icon: Icons.cancel_rounded,
                          color: const Color(0xFFDC2626),
                          metaLabel: "Off Campus",
                          metaBadge: "$absentToday Pending",
                          hasPulsePip: true,
                        ),
                        _buildKpiCard(
                          title: "Att. Rate",
                          value: "$rate%",
                          icon: Icons.pie_chart_rounded,
                          color: const Color(0xFFD97706),
                          metaLabel: "Goal: 75%",
                          metaBadge: "Quorum",
                          progressPercent: double.tryParse(rate) ?? 0.0,
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),

                    // Today's Live Attendance Feed
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          "Today's Activity Feed",
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          "${_todayScans.length} logged",
                          style: const TextStyle(color: Colors.grey, fontSize: 13),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    if (_todayScans.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(32),
                        alignment: Alignment.center,
                        child: Column(
                          children: [
                            Icon(Icons.event_available,
                                size: 48,
                                color: Colors.grey.withValues(alpha: 0.5)),
                            const SizedBox(height: 8),
                            const Text(
                              "No attendance recorded today yet",
                              style: TextStyle(color: Colors.grey),
                            ),
                          ],
                        ),
                      )
                    else
                      ListView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: _todayScans.length,
                        itemBuilder: (ctx, i) {
                          final rec = _todayScans[i];
                          final student = rec['student'] ?? {};
                          final status = rec['status'] ?? 'Present';
                          final isPresent = status == 'Present';

                          return Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor: isPresent
                                    ? Colors.green.withValues(alpha: 0.15)
                                    : Colors.red.withValues(alpha: 0.15),
                                foregroundColor:
                                    isPresent ? Colors.green : Colors.red,
                                child: Text(
                                  (student['full_name'] ?? 'S')[0].toUpperCase(),
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold),
                                ),
                              ),
                              title: Text(
                                student['full_name'] ?? 'Student',
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold),
                              ),
                              subtitle: Text(
                                "In: ${rec['time_in'] ?? '-'}  •  Out: ${rec['time_out'] ?? '-'}",
                                style: const TextStyle(fontSize: 12),
                              ),
                              trailing: Chip(
                                label: Text(status),
                                backgroundColor: isPresent
                                    ? Colors.green.withValues(alpha: 0.15)
                                    : Colors.red.withValues(alpha: 0.15),
                                labelStyle: TextStyle(
                                  color: isPresent ? Colors.green : Colors.red,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                                visualDensity: VisualDensity.compact,
                              ),
                            ),
                          );
                        },
                      ),
                  ],
                ),
              ),
            ),
    );
  }
}
