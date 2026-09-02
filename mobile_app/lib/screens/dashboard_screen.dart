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

  Widget _buildKpiCard(String title, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  title.toUpperCase(),
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.5,
                    color: Colors.grey,
                  ),
                ),
                Icon(icon, color: color, size: 20),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              value,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: color,
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
                    // KPI Grid
                    GridView.count(
                      crossAxisCount: 2,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      childAspectRatio: 1.4,
                      children: [
                        _buildKpiCard("Total Students", totalStudents,
                            Icons.people_alt, const Color(0xFF3B82F6)),
                        _buildKpiCard("Present Today", presentToday,
                            Icons.how_to_reg, const Color(0xFF10B981)),
                        _buildKpiCard("Absent Today", absentToday,
                            Icons.person_off, const Color(0xFFEF4444)),
                        _buildKpiCard("Attendance Rate", "$rate%",
                            Icons.pie_chart, const Color(0xFFF59E0B)),
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
