import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:mobile_app/services/api_service.dart';
import 'package:mobile_app/screens/scanner_screen.dart';

class TakeAttendanceScreen extends StatefulWidget {
  const TakeAttendanceScreen({super.key});

  @override
  State<TakeAttendanceScreen> createState() => _TakeAttendanceScreenState();
}

class _TakeAttendanceScreenState extends State<TakeAttendanceScreen> {
  String _attendanceMode = 'SUBJECT'; // 'SUBJECT', 'GENERAL', 'COMBINED'
  List<Map<String, dynamic>> _subjects = [];
  List<Map<String, dynamic>> _coordinatorAssignments = [];
  bool _loadingSubjects = true;

  int? _selectedSubjectId;
  String? _selectedSemester;
  String? _selectedSection = 'All';

  List<Map<String, dynamic>> _roster = [];
  final Map<dynamic, String> _studentStatusMap = {}; // id -> 'Present' | 'Absent'
  bool _loadingRoster = false;
  String _searchQuery = '';
  bool _isSubmitting = false;

  String? _rosterErrorMessage;
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _fetchSubjects();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  String _normalizeSemester(String? sem) {
    if (sem == null || sem.isEmpty) return 'All Semesters';
    final s = sem.trim().toLowerCase();
    if (s == 'all' || s == 'any' || s == 'all semesters' || s == 'general') {
      return 'All Semesters';
    }
    final digits = RegExp(r'\d+').firstMatch(s);
    if (digits != null) {
      final d = digits.group(0);
      switch (d) {
        case '1': return '1st Semester';
        case '2': return '2nd Semester';
        case '3': return '3rd Semester';
        case '4': return '4th Semester';
        case '5': return '5th Semester';
        case '6': return '6th Semester';
        case '7': return '7th Semester';
        case '8': return '8th Semester';
      }
    }
    return 'All Semesters';
  }

  String _normalizeSection(String? sec) {
    if (sec == null || sec.isEmpty || sec.toLowerCase() == 'none' || sec.toLowerCase() == 'all') {
      return 'All';
    }
    final upper = sec.trim().toUpperCase();
    if (['A', 'B', 'C'].contains(upper)) {
      return upper;
    }
    return 'All';
  }

  Future<void> _fetchSubjects() async {
    final user = ApiService().currentUser;
    List<dynamic> list = [];
    List<Map<String, dynamic>> coords = [];

    if (user != null && user['role'] == 'teacher') {
      final res = await ApiService().getTeacherSubjectsData();
      list = res['subjects'] as List<dynamic>? ?? [];
      final rawCoords = res['coordinator_assignments'] as List<dynamic>? ?? [];
      coords = rawCoords.map((e) => Map<String, dynamic>.from(e)).toList();
    } else {
      list = await ApiService().getSubjects();
    }

    if (mounted) {
      setState(() {
        _subjects = list.map((e) => Map<String, dynamic>.from(e)).toList();
        _coordinatorAssignments = coords;
        _loadingSubjects = false;

        if (_subjects.isEmpty && _coordinatorAssignments.isNotEmpty) {
          _attendanceMode = 'GENERAL';
        } else {
          _attendanceMode = 'SUBJECT';
        }

        if (_subjects.isNotEmpty) {
          final first = _subjects.first;
          _selectedSubjectId = first['subject_id'] ?? first['id'];
          _selectedSemester = _normalizeSemester(first['semester']?.toString());
          _selectedSection = _normalizeSection(first['section']?.toString());
        } else if (_coordinatorAssignments.isNotEmpty) {
          final firstCoord = _coordinatorAssignments.first;
          _selectedSemester = _normalizeSemester(firstCoord['semester']?.toString());
          _selectedSection = _normalizeSection(firstCoord['section']?.toString());
        } else {
          _selectedSemester = 'All Semesters';
          _selectedSection = 'All';
        }
      });

      _loadRoster();
    }
  }

  Future<void> _loadRoster() async {
    if (_attendanceMode != 'GENERAL' && _selectedSubjectId == null) {
      if (mounted) {
        setState(() {
          _loadingRoster = false;
          _roster = [];
          _studentStatusMap.clear();
          _rosterErrorMessage = null;
        });
      }
      return;
    }

    setState(() {
      _loadingRoster = true;
      _rosterErrorMessage = null;
    });

    final semParam = (_selectedSemester == null || _selectedSemester == 'All Semesters')
        ? 'All'
        : _selectedSemester;

    final res = await ApiService().getRoster(
      subjectId: _attendanceMode == 'GENERAL' ? null : _selectedSubjectId,
      semester: semParam,
      section: _selectedSection == 'All' ? null : _selectedSection,
      attendanceType: _attendanceMode,
    );

    if (mounted) {
      setState(() {
        _loadingRoster = false;
        if (res['success'] == true) {
          _rosterErrorMessage = null;
          final rawList = res['students'] as List<dynamic>? ?? [];
          _roster = rawList.map((e) => Map<String, dynamic>.from(e)).toList();
          _studentStatusMap.clear();

          // Seed previously marked attendance if any
          for (final s in _roster) {
            final id = s['id'] ?? s['student_id'];
            if (s['current_status'] == 'Present') {
              _studentStatusMap[id] = 'Present';
            } else if (s['current_status'] == 'Absent') {
              _studentStatusMap[id] = 'Absent';
            }
          }
        } else {
          _roster = [];
          _studentStatusMap.clear();
          _rosterErrorMessage = res['message']?.toString() ?? 'Failed to load roster.';
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(_rosterErrorMessage!),
              backgroundColor: Colors.redAccent,
            ),
          );
        }
      });
    }
  }

  void _onSubjectChanged(int? newSubId) {
    if (newSubId == null || newSubId == _selectedSubjectId) return;

    final found = _subjects.firstWhere(
      (s) => (s['subject_id'] ?? s['id']) == newSubId,
      orElse: () => {},
    );

    setState(() {
      _selectedSubjectId = newSubId;
      if (found.isNotEmpty) {
        _selectedSemester = _normalizeSemester(found['semester']?.toString());
        _selectedSection = _normalizeSection(found['section']?.toString());
      }
      _roster = [];
      _studentStatusMap.clear();
      _rosterErrorMessage = null;
    });

    _loadRoster();
  }

  void _toggleStudent(dynamic id) {
    setState(() {
      if (_studentStatusMap[id] == 'Present') {
        _studentStatusMap.remove(id); // unmarked -> will be absent on submit
      } else {
        _studentStatusMap[id] = 'Present';
      }
    });
  }

  void _markAllPresent() {
    setState(() {
      for (final s in _roster) {
        final id = s['id'] ?? s['student_id'];
        _studentStatusMap[id] = 'Present';
      }
    });
  }

  void _clearAllMarks() {
    setState(() {
      _studentStatusMap.clear();
    });
  }

  void _markAllAbsent() {
    setState(() {
      for (final s in _roster) {
        final id = s['id'] ?? s['student_id'];
        _studentStatusMap[id] = 'Absent';
      }
    });
  }

  List<Map<String, dynamic>> get _filteredRoster {
    if (_searchQuery.trim().isEmpty) return _roster;
    final q = _searchQuery.trim().toLowerCase();
    return _roster.where((s) {
      final name = (s['full_name'] ?? s['name'] ?? '').toString().toLowerCase();
      final sid = (s['student_id'] ?? '').toString().toLowerCase();
      final roll = (s['roll_number'] ?? '').toString().toLowerCase();
      return name.contains(q) || sid.contains(q) || roll.contains(q);
    }).toList();
  }

  int get _presentCount {
    int c = 0;
    for (final s in _roster) {
      final id = s['id'] ?? s['student_id'];
      if (_studentStatusMap[id] == 'Present') c++;
    }
    return c;
  }

  int get _absentCount {
    return _roster.length - _presentCount; // Unmarked automatically becomes absent!
  }

  Future<void> _confirmAndSubmit() async {
    if (_roster.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("No students in roster to submit attendance.")),
      );
      return;
    }

    final total = _roster.length;
    final present = _presentCount;
    final absent = _absentCount;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Row(
          children: [
            Icon(Icons.shield_outlined, color: Color(0xFF2563EB)),
            SizedBox(width: 8),
            Text("Attendance Summary"),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _attendanceMode == 'GENERAL'
                        ? "General Daily Attendance"
                        : "Subject: ${_subjects.firstWhere((s) => (s['subject_id'] ?? s['id']) == _selectedSubjectId, orElse: () => {})['name'] ?? 'Subject'}",
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    "Semester: $_selectedSemester  •  Section: $_selectedSection",
                    style: const TextStyle(fontSize: 12, color: Colors.black54),
                  ),
                  Text(
                    "Date: ${DateFormat('dd MMM yyyy').format(DateTime.now())}",
                    style: const TextStyle(fontSize: 12, color: Colors.black54),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStatTile("Total", "$total", Colors.blue),
                _buildStatTile("Present", "$present", const Color(0xFF10B981)),
                _buildStatTile("Absent", "$absent", Colors.redAccent),
              ],
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.amber.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.amber.withValues(alpha: 0.4)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.info_outline, size: 18, color: Colors.amber),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      "Unmarked students will automatically be saved as Absent.",
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text("Back to List"),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF2563EB),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text("Confirm & Submit"),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() {
      _isSubmitting = true;
    });

    final presentIds = <dynamic>[];
    for (final s in _roster) {
      final id = s['id'] ?? s['student_id'];
      if (_studentStatusMap[id] == 'Present') {
        presentIds.add(s['id'] ?? s['student_id']);
      }
    }

    final res = await ApiService().submitBulkAttendance(
      presentStudentIds: presentIds,
      subjectId: _attendanceMode == 'GENERAL' ? null : _selectedSubjectId,
      semester: _selectedSemester,
      section: _selectedSection == 'All' ? null : _selectedSection,
      attendanceType: _attendanceMode,
    );

    if (!mounted) return;

    setState(() {
      _isSubmitting = false;
    });

    if (res['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(res['message']?.toString() ?? "Attendance successfully saved!"),
          backgroundColor: const Color(0xFF10B981),
          duration: const Duration(seconds: 4),
        ),
      );
      _loadRoster();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(res['message']?.toString() ?? "Submission failed. Please retry."),
          backgroundColor: Colors.redAccent,
        ),
      );
    }
  }

  Widget _buildStatTile(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color)),
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.black54)),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final total = _roster.length;
    final present = _presentCount;
    final absent = _absentCount;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Take Attendance", style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.qr_code_scanner_rounded),
            tooltip: "Switch to Camera Scanner",
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ScannerScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: "Refresh Roster",
            onPressed: _loadRoster,
          ),
        ],
      ),
      body: _loadingSubjects
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Mode selector if coordinator or admin
                if (_coordinatorAssignments.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                    child: SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(value: 'SUBJECT', label: Text("Subject")),
                        ButtonSegment(value: 'GENERAL', label: Text("General")),
                        ButtonSegment(value: 'COMBINED', label: Text("Combined")),
                      ],
                      selected: {_attendanceMode},
                      onSelectionChanged: (val) {
                        setState(() {
                          _attendanceMode = val.first;
                        });
                        _loadRoster();
                      },
                    ),
                  ),

                // Controls: Subject, Semester, Section
                Card(
                  margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  elevation: 1,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (_attendanceMode != 'GENERAL')
                          if (_subjects.length == 1)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                              decoration: BoxDecoration(
                                color: Colors.blue.withValues(alpha: 0.08),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.book_outlined, size: 18, color: Color(0xFF2563EB)),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      "${_subjects.first['code'] ?? _subjects.first['subject_code']} - ${_subjects.first['name'] ?? _subjects.first['subject_name']}",
                                      style: const TextStyle(fontWeight: FontWeight.bold),
                                    ),
                                  ),
                                  const Chip(
                                    label: Text("Auto", style: TextStyle(fontSize: 10)),
                                    padding: EdgeInsets.zero,
                                    visualDensity: VisualDensity.compact,
                                  ),
                                ],
                              ),
                            )
                          else if (_subjects.isNotEmpty)
                            DropdownButtonFormField<int>(
                              key: ValueKey('subj_$_selectedSubjectId'),
                              initialValue: _selectedSubjectId,
                              decoration: const InputDecoration(
                                labelText: "Subject",
                                isDense: true,
                                contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                              ),
                              isExpanded: true,
                              items: _subjects.map((s) {
                                final sid = (s['subject_id'] ?? s['id']) as int;
                                final code = s['code'] ?? s['subject_code'] ?? '';
                                final name = s['name'] ?? s['subject_name'] ?? '';
                                return DropdownMenuItem<int>(
                                  value: sid,
                                  child: Text("$code - $name", overflow: TextOverflow.ellipsis),
                                );
                              }).toList(),
                              onChanged: _onSubjectChanged,
                            ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Expanded(
                              flex: 3,
                              child: DropdownButtonFormField<String>(
                                key: ValueKey('sem_$_selectedSemester'),
                                initialValue: _selectedSemester ?? 'All Semesters',
                                decoration: const InputDecoration(
                                  labelText: "Semester",
                                  isDense: true,
                                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                ),
                                items: [
                                  'All Semesters',
                                  '1st Semester',
                                  '2nd Semester',
                                  '3rd Semester',
                                  '4th Semester',
                                  '5th Semester',
                                  '6th Semester',
                                  '7th Semester',
                                  '8th Semester',
                                ].map((sem) => DropdownMenuItem(value: sem, child: Text(sem))).toList(),
                                onChanged: (val) {
                                  setState(() {
                                    _selectedSemester = val;
                                  });
                                  _loadRoster();
                                },
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              flex: 2,
                              child: DropdownButtonFormField<String>(
                                key: ValueKey('sec_$_selectedSection'),
                                initialValue: _selectedSection ?? 'All',
                                decoration: const InputDecoration(
                                  labelText: "Section",
                                  isDense: true,
                                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                ),
                                items: ['All', 'A', 'B', 'C']
                                    .map((sec) => DropdownMenuItem(value: sec, child: Text("Sec $sec")))
                                    .toList(),
                                onChanged: (val) {
                                  setState(() {
                                    _selectedSection = val;
                                  });
                                  _loadRoster();
                                },
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),

                // Live Counters Pill Bar
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                  child: Row(
                    children: [
                      _buildCountBadge("Total: $total", Colors.grey.shade700, Colors.grey.withValues(alpha: 0.15)),
                      const SizedBox(width: 8),
                      _buildCountBadge("Present: $present", const Color(0xFF10B981), const Color(0xFF10B981).withValues(alpha: 0.15)),
                      const SizedBox(width: 8),
                      _buildCountBadge("Absent: $absent", Colors.redAccent, Colors.redAccent.withValues(alpha: 0.15)),
                    ],
                  ),
                ),

                // Search Bar & Bulk Actions
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _searchController,
                          decoration: InputDecoration(
                            hintText: "Search student...",
                            prefixIcon: const Icon(Icons.search, size: 20),
                            isDense: true,
                            contentPadding: const EdgeInsets.symmetric(vertical: 8),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                            suffixIcon: _searchQuery.isNotEmpty
                                ? IconButton(
                                    icon: const Icon(Icons.clear, size: 16),
                                    onPressed: () {
                                      _searchController.clear();
                                      setState(() {
                                        _searchQuery = '';
                                      });
                                    },
                                  )
                                : null,
                          ),
                          onChanged: (val) {
                            setState(() {
                              _searchQuery = val;
                            });
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        icon: const Icon(Icons.check_circle_outline_rounded, color: Color(0xFF10B981)),
                        tooltip: "Mark All Present",
                        onPressed: _markAllPresent,
                      ),
                      IconButton(
                        icon: const Icon(Icons.restart_alt_rounded, color: Colors.grey),
                        tooltip: "Clear All",
                        onPressed: _clearAllMarks,
                      ),
                      IconButton(
                        icon: const Icon(Icons.highlight_off_rounded, color: Colors.redAccent),
                        tooltip: "Mark All Absent",
                        onPressed: _markAllAbsent,
                      ),
                    ],
                  ),
                ),

                // Student List View
                Expanded(
                  child: _loadingRoster
                      ? const Center(child: CircularProgressIndicator())
                      : _rosterErrorMessage != null
                          ? Center(
                              child: Padding(
                                padding: const EdgeInsets.all(24),
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    const Icon(Icons.error_outline_rounded, size: 48, color: Colors.redAccent),
                                    const SizedBox(height: 12),
                                    Text(
                                      _rosterErrorMessage!,
                                      textAlign: TextAlign.center,
                                      style: const TextStyle(color: Colors.redAccent, fontWeight: FontWeight.w600),
                                    ),
                                    const SizedBox(height: 16),
                                    ElevatedButton.icon(
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor: const Color(0xFF2563EB),
                                        foregroundColor: Colors.white,
                                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                      ),
                                      onPressed: _loadRoster,
                                      icon: const Icon(Icons.refresh_rounded, size: 18),
                                      label: const Text("Retry"),
                                    ),
                                  ],
                                ),
                              ),
                            )
                          : _filteredRoster.isEmpty
                              ? Center(
                                  child: Padding(
                                    padding: const EdgeInsets.all(24),
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.group_off_rounded, size: 48, color: Colors.grey.shade400),
                                        const SizedBox(height: 12),
                                        Text(
                                          "No students found in ${_selectedSemester ?? 'this semester'} (Sec ${_selectedSection ?? 'All'}).",
                                          textAlign: TextAlign.center,
                                          style: const TextStyle(color: Colors.black87, fontWeight: FontWeight.w500),
                                        ),
                                        const SizedBox(height: 16),
                                        Wrap(
                                          spacing: 8,
                                          runSpacing: 8,
                                          alignment: WrapAlignment.center,
                                          children: [
                                            if (_selectedSemester != 'All Semesters')
                                              OutlinedButton.icon(
                                                icon: const Icon(Icons.filter_alt_off_rounded, size: 16),
                                                label: const Text("Show All Semesters"),
                                                onPressed: () {
                                                  setState(() {
                                                    _selectedSemester = 'All Semesters';
                                                  });
                                                  _loadRoster();
                                                },
                                              ),
                                            OutlinedButton.icon(
                                              icon: const Icon(Icons.refresh_rounded, size: 16),
                                              label: const Text("Refresh"),
                                              onPressed: _loadRoster,
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),
                                )
                              : RefreshIndicator(
                                  onRefresh: _loadRoster,
                                  child: ListView.builder(
                                    physics: const AlwaysScrollableScrollPhysics(),
                                    padding: const EdgeInsets.fromLTRB(12, 4, 12, 80),
                                    itemCount: _filteredRoster.length,
                                    itemBuilder: (ctx, idx) {
                                      final s = _filteredRoster[idx];
                                      final id = s['id'] ?? s['student_id'];
                                      final isPresent = _studentStatusMap[id] == 'Present';
                                      final name = s['full_name'] ?? s['name'] ?? 'Student';
                                      final roll = s['roll_number'] ?? '-';
                                      final sid = s['student_id'] ?? '';
                                      final sec = s['section'] ?? '';

                                      return Card(
                                        margin: const EdgeInsets.symmetric(vertical: 4),
                                        shape: RoundedRectangleBorder(
                                          borderRadius: BorderRadius.circular(12),
                                          side: BorderSide(
                                            color: isPresent
                                                ? const Color(0xFF10B981).withValues(alpha: 0.6)
                                                : Colors.transparent,
                                            width: 1.5,
                                          ),
                                        ),
                                        color: isPresent
                                            ? const Color(0xFF10B981).withValues(alpha: isDark ? 0.15 : 0.08)
                                            : null,
                                        child: ListTile(
                                          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                                          leading: CircleAvatar(
                                            backgroundColor: isPresent
                                                ? const Color(0xFF10B981)
                                                : const Color(0xFF2563EB).withValues(alpha: 0.15),
                                            foregroundColor: isPresent ? Colors.white : const Color(0xFF2563EB),
                                            child: Text(
                                              name.isNotEmpty ? name[0].toUpperCase() : "S",
                                              style: const TextStyle(fontWeight: FontWeight.bold),
                                            ),
                                          ),
                                          title: Text(name, style: const TextStyle(fontWeight: FontWeight.bold)),
                                          subtitle: Text(
                                            "Roll: $roll • $sid ${sec.isNotEmpty ? '• Sec $sec' : ''}",
                                            style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                                          ),
                                          trailing: ElevatedButton.icon(
                                            style: ElevatedButton.styleFrom(
                                              backgroundColor: isPresent
                                                  ? const Color(0xFF10B981)
                                                  : Colors.grey.withValues(alpha: 0.15),
                                              foregroundColor: isPresent ? Colors.white : Colors.grey.shade700,
                                              elevation: isPresent ? 2 : 0,
                                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                            ),
                                            icon: Icon(
                                              isPresent ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                                              size: 16,
                                            ),
                                            label: Text(
                                              isPresent ? "Present" : "Unmarked",
                                              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                                            ),
                                            onPressed: () => _toggleStudent(id),
                                          ),
                                          onTap: () => _toggleStudent(id),
                                        ),
                                      );
                                    },
                                  ),
                                ),
                ),
              ],
            ),
      bottomSheet: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: theme.scaffoldBackgroundColor,
          boxShadow: [
            BoxShadow(color: Colors.black.withValues(alpha: 0.1), blurRadius: 10, offset: const Offset(0, -2)),
          ],
        ),
        child: SafeArea(
          child: SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF2563EB),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              icon: _isSubmitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.cloud_upload_rounded),
              label: Text(
                _isSubmitting
                    ? "Submitting..."
                    : "Submit Attendance ($_presentCount Present, $_absentCount Absent)",
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
              ),
              onPressed: (_loadingRoster || _isSubmitting) ? null : _confirmAndSubmit,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCountBadge(String text, Color textColor, Color bgColor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bgColor, borderRadius: BorderRadius.circular(20)),
      child: Text(text, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: textColor)),
    );
  }
}
