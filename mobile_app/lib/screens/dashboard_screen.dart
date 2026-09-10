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
  Map<String, dynamic>? _studentAttendanceSummary;
  List<dynamic> _teacherSubjects = [];
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

    final user = ApiService().currentUser;
    final isStudent = user != null && user['role'] == 'student';
    final isTeacher = user != null && user['role'] == 'teacher';

    final stats = await ApiService().getDashboardStats();
    final scans = await ApiService().getTodayAttendance();
    Map<String, dynamic>? studentSummary;
    List<dynamic> teacherSubs = [];

    if (isStudent) {
      studentSummary = await ApiService().getStudentAttendanceSummary();
    } else if (isTeacher) {
      teacherSubs = await ApiService().getTeacherSubjects();
    }

    if (mounted) {
      setState(() {
        _stats = stats;
        _todayScans = scans;
        _studentAttendanceSummary = studentSummary;
        _teacherSubjects = teacherSubs;
        _isLoading = false;
      });
    }
  }

  Color _getPercentageColor(double percentage) {
    if (percentage >= 75.0) return const Color(0xFF10B981); // Green
    if (percentage >= 60.0) return const Color(0xFFF59E0B); // Amber
    return const Color(0xFFEF4444); // Red
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

  void _showSubjectDetailBottomSheet(Map<String, dynamic> subject) {
    final subId = subject['subject_id'] as int? ?? subject['id'] as int? ?? 0;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return FutureBuilder<Map<String, dynamic>?>(
          future: ApiService().getStudentSubjectAttendanceDetail(subId),
          builder: (context, snapshot) {
            final loading = snapshot.connectionState == ConnectionState.waiting;
            final data = snapshot.data;
            final history = (data?['history'] as List<dynamic>?) ?? [];
            final sub = (data?['subject'] as Map<String, dynamic>?) ?? subject;
            final percentage = (sub['percentage'] is num) ? (sub['percentage'] as num).toDouble() : 0.0;
            final color = _getPercentageColor(percentage);

            return Container(
              height: MediaQuery.of(context).size.height * 0.75,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Theme.of(context).scaffoldBackgroundColor,
                borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.grey.withValues(alpha: 0.3),
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              sub['subject_name'] ?? sub['name'] ?? 'Subject',
                              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 2),
                            Text(
                              "Code: ${sub['subject_code'] ?? sub['code'] ?? '-'} • Faculty: ${sub['teacher'] ?? 'Unassigned'}",
                              style: TextStyle(fontSize: 12, color: isDark ? Colors.grey.shade400 : Colors.grey.shade700),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: color.withValues(alpha: 0.3)),
                        ),
                        child: Text(
                          "${percentage.toStringAsFixed(1)}%",
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: color),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // 3-metric summary row
                  Container(
                    padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF1E293B) : Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _buildMiniMetric("Conducted", "${sub['total'] ?? 0}"),
                        _buildMiniMetric("Present", "${sub['present'] ?? 0}", color: Colors.green),
                        _buildMiniMetric("Absent", "${sub['absent'] ?? 0}", color: Colors.redAccent),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  const Text(
                    "Attendance History",
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),

                  Expanded(
                    child: loading
                        ? const Center(child: CircularProgressIndicator())
                        : history.isEmpty
                            ? const Center(
                                child: Text("No individual records found for this subject",
                                    style: TextStyle(color: Colors.grey)),
                              )
                            : ListView.separated(
                                itemCount: history.length,
                                separatorBuilder: (_, _) => const Divider(height: 1),
                                itemBuilder: (c, i) {
                                  final rec = history[i];
                                  final isPresent = rec['status'] == 'Present';
                                  return ListTile(
                                    dense: true,
                                    leading: CircleAvatar(
                                      radius: 12,
                                      backgroundColor: isPresent ? Colors.green : Colors.redAccent,
                                      child: Icon(
                                        isPresent ? Icons.check : Icons.close,
                                        color: Colors.white,
                                        size: 14,
                                      ),
                                    ),
                                    title: Text(
                                      rec['date'] ?? '-',
                                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                    ),
                                    subtitle: Text(
                                      "Time: ${rec['time_in'] ?? '-'} • Via: ${rec['method'] ?? 'QR'}",
                                      style: const TextStyle(fontSize: 11),
                                    ),
                                    trailing: Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: (isPresent ? Colors.green : Colors.redAccent).withValues(alpha: 0.15),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        rec['status'] ?? '-',
                                        style: TextStyle(
                                          fontSize: 11,
                                          fontWeight: FontWeight.bold,
                                          color: isPresent ? Colors.green : Colors.redAccent,
                                        ),
                                      ),
                                    ),
                                  );
                                },
                              ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildMiniMetric(String label, String value, {Color? color}) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: Colors.grey),
        ),
      ],
    );
  }

  Widget _buildStudentAttendanceView() {
    final summary = _studentAttendanceSummary ?? {};
    final overall = (summary['overall'] as Map<String, dynamic>?) ?? {};
    final subjects = (summary['subjects'] as List<dynamic>?) ?? [];
    final overallRate = (overall['rate'] is num) ? (overall['rate'] as num).toDouble() : 0.0;
    final totalClasses = overall['total'] ?? 0;
    final presentClasses = overall['present'] ?? 0;
    final absentClasses = overall['absent'] ?? 0;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Overall Attendance Card
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF1E3A8A), Color(0xFF2563EB)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      "OVERALL ATTENDANCE",
                      style: TextStyle(
                        color: Colors.white70,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.5,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        "${overallRate.toStringAsFixed(1)}%",
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      "${overallRate.toStringAsFixed(1)}%",
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 32,
                        fontWeight: FontWeight.w900,
                        fontFamily: 'monospace',
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Text(
                      "Attendance Rate",
                      style: TextStyle(color: Colors.white70, fontSize: 13),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: LinearProgressIndicator(
                    value: (overallRate / 100.0).clamp(0.0, 1.0),
                    backgroundColor: Colors.white.withValues(alpha: 0.2),
                    valueColor: const AlwaysStoppedAnimation<Color>(Colors.greenAccent),
                    minHeight: 8,
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      "Conducted: $totalClasses classes",
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                    Text(
                      "Present: $presentClasses  •  Absent: $absentClasses",
                      style: const TextStyle(color: Colors.white70, fontSize: 12),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // SUBJECT-WISE ATTENDANCE SECTION
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                "SUBJECT-WISE ATTENDANCE",
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                ),
              ),
              Chip(
                label: Text("${subjects.length} Subjects"),
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
          const SizedBox(height: 12),

          if (subjects.isEmpty)
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF1E293B) : Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
              ),
              alignment: Alignment.center,
              child: const Column(
                children: [
                  Icon(Icons.menu_book_rounded, size: 40, color: Colors.grey),
                  SizedBox(height: 8),
                  Text(
                    "No subject attendance records found yet",
                    style: TextStyle(color: Colors.grey, fontSize: 13),
                  ),
                ],
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: subjects.length,
              separatorBuilder: (_, _) => const SizedBox(height: 12),
              itemBuilder: (ctx, i) {
                final sub = Map<String, dynamic>.from(subjects[i]);
                final pct = (sub['percentage'] is num) ? (sub['percentage'] as num).toDouble() : 0.0;
                final color = _getPercentageColor(pct);

                return InkWell(
                  onTap: () => _showSubjectDetailBottomSheet(sub),
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF1E293B) : Colors.white,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.grey.withValues(alpha: 0.15)),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: isDark ? 0.2 : 0.03),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    sub['subject_name'] ?? 'Subject',
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    "${sub['subject_code']} • Faculty: ${sub['teacher'] ?? 'Faculty'}",
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                              decoration: BoxDecoration(
                                color: color.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                "${pct.toStringAsFixed(1)}%",
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13,
                                  color: color,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: (pct / 100.0).clamp(0.0, 1.0),
                            backgroundColor: isDark ? Colors.white10 : Colors.grey.shade200,
                            valueColor: AlwaysStoppedAnimation<Color>(color),
                            minHeight: 6,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              "Present: ${sub['present']}  •  Total: ${sub['total']}",
                              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
                            ),
                            Row(
                              children: [
                                Text(
                                  "View Details",
                                  style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.primary),
                                ),
                                Icon(Icons.chevron_right, size: 14, color: Theme.of(context).colorScheme.primary),
                              ],
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),

          const SizedBox(height: 24),
          _buildPresentTodaySection(),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildTeacherSubjectsSection() {
    if (_teacherSubjects.isEmpty) return const SizedBox.shrink();

    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              "MY ASSIGNED SUBJECTS",
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, letterSpacing: 0.5),
            ),
            Chip(
              label: Text("${_teacherSubjects.length} Assigned"),
              visualDensity: VisualDensity.compact,
            ),
          ],
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: 90,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: _teacherSubjects.length,
            separatorBuilder: (_, _) => const SizedBox(width: 10),
            itemBuilder: (c, i) {
              final sub = _teacherSubjects[i];
              return Container(
                width: 160,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF1E293B) : Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: Colors.blue.withValues(alpha: 0.3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.blue.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        sub['subject_code'] ?? '',
                        style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.blue),
                      ),
                    ),
                    Text(
                      sub['subject_name'] ?? '',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 20),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = ApiService().currentUser;
    final isStudent = user != null && user['role'] == 'student';
    final isTeacher = user != null && user['role'] == 'teacher';

    final totalStudents = _stats['total_students']?.toString() ?? "0";
    final presentToday = _stats['present_today']?.toString() ?? "0";
    final absentToday = _stats['absent_today']?.toString() ?? "0";
    final rate = _stats['attendance_rate']?.toString() ?? "0";

    return Scaffold(
      appBar: AppBar(
        title: Text(isStudent ? "My Attendance" : "ERP Analytics Dashboard"),
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
              child: isStudent
                  ? _buildStudentAttendanceView()
                  : SingleChildScrollView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (isTeacher) _buildTeacherSubjectsSection(),

                          // KPI Grid
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

                          // PRESENT TODAY Section
                          _buildPresentTodaySection(),
                          const SizedBox(height: 16),
                        ],
                      ),
                    ),
            ),
    );
  }

  List<Map<String, dynamic>> _getPresentStudentsList() {
    final list = <Map<String, dynamic>>[];
    final seen = <String>{};

    for (final rec in _todayScans) {
      final status = rec['status'] ?? '';
      if (status == 'Present' || status == 'Late' || status == 'Half Day') {
        final s = (rec['student'] is Map ? rec['student'] : null) ?? {};
        final name = rec['student_name'] ?? s['full_name'] ?? 'Unknown Student';
        final id = rec['student_id'] ?? s['student_id'] ?? '';
        final sub = (rec['subject'] is Map ? rec['subject'] : null) ?? {};
        final subName = sub['code'] ?? sub['name'] ?? '';

        final key = "${id.isNotEmpty ? id : name}_$subName";
        if (!seen.contains(key)) {
          seen.add(key);
          list.add({
            'full_name': name,
            'student_id': id,
            'time_in': rec['time_in'] ?? '-',
            'subject': subName,
          });
        }
      }
    }

    if (list.isEmpty &&
        _stats['present_students'] is List &&
        (_stats['present_students'] as List).isNotEmpty) {
      return (_stats['present_students'] as List)
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
    }

    return list;
  }

  Widget _buildPresentTodaySection() {
    final presentStudents = _getPresentStudentsList();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              "PRESENT TODAY — ${presentStudents.length}",
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.green.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                "${presentStudents.length} Marked",
                style: const TextStyle(
                  color: Colors.green,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (presentStudents.isEmpty)
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF1E293B) : Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
            ),
            alignment: Alignment.center,
            child: const Text(
              "No students marked present yet today",
              style: TextStyle(color: Colors.grey),
            ),
          )
        else
          Container(
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF1E293B) : Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
            ),
            child: ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: presentStudents.length,
              separatorBuilder: (_, _) => Divider(
                height: 1,
                color: Colors.grey.withValues(alpha: 0.15),
              ),
              itemBuilder: (ctx, idx) {
                final s = presentStudents[idx];
                final name = s['full_name'] ?? 'Unknown Student';
                final studentId = s['student_id'] ?? '';
                final timeIn = s['time_in'] ?? '-';
                final subject = s['subject']?.toString() ?? '';

                return ListTile(
                  dense: true,
                  leading: CircleAvatar(
                    radius: 14,
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                    child: Text(
                      "${idx + 1}",
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  title: Text(
                    name,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(
                    "${studentId.isNotEmpty ? '$studentId • ' : ''}Time In: $timeIn${subject.isNotEmpty ? ' • [$subject]' : ''}",
                    style: const TextStyle(fontSize: 11),
                  ),
                  trailing: const Icon(
                    Icons.check_circle,
                    color: Colors.green,
                    size: 18,
                  ),
                );
              },
            ),
          ),
      ],
    );
  }
}
