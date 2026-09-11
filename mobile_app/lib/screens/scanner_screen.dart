import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:mobile_app/services/api_service.dart';

class ScannerScreen extends StatefulWidget {
  const ScannerScreen({super.key});

  @override
  State<ScannerScreen> createState() => _ScannerScreenState();
}

class _ScannerScreenState extends State<ScannerScreen> {
  final MobileScannerController _scannerController = MobileScannerController(
    detectionSpeed: DetectionSpeed.normal,
    facing: CameraFacing.back,
    torchEnabled: false,
  );

  bool _isProcessing = false;
  bool _isSheetOpen = false;
  String? _lastScannedToken;
  DateTime _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
  final List<Map<String, dynamic>> _sessionScans = [];

  List<Map<String, dynamic>> _subjects = [];
  List<Map<String, dynamic>> _coordinatorAssignments = [];
  String _attendanceMode = 'SUBJECT'; // 'GENERAL' vs 'SUBJECT'
  int? _selectedSubjectId;
  String? _selectedSemester;
  String? _selectedTeacherName;
  String? _selectedSubjectCode;
  String? _selectedSubjectName;
  String? _selectedDept;
  String? _selectedCourse;
  String? _selectedSection;
  String? _selectedSubjectLabel;
  int _selectedSubjectIndex = 0;
  bool _loadingSubjects = true;
  bool _isScanningActive = true;

  @override
  void initState() {
    super.initState();
    _isScanningActive = true;
    _fetchSubjects();
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

        // If teacher is assigned as coordinator and has no subjects, default to GENERAL
        if (_subjects.isEmpty && _coordinatorAssignments.isNotEmpty) {
          _attendanceMode = 'GENERAL';
        } else {
          _attendanceMode = 'SUBJECT';
        }

        if (_subjects.isNotEmpty) {
          _selectSubjectAtIndex(0);
        }
      });
    }
  }

  void _selectSubjectAtIndex(int index) {
    if (index < 0 || index >= _subjects.length) return;
    final item = _subjects[index];
    _selectedSubjectIndex = index;

    final rawSubId = item['subject_id'] ?? item['id'];
    if (rawSubId is int) {
      _selectedSubjectId = rawSubId;
    } else if (rawSubId != null) {
      _selectedSubjectId = int.tryParse(rawSubId.toString());
    } else {
      _selectedSubjectId = null;
    }

    _selectedSemester = item['semester']?.toString();
    _selectedTeacherName = item['teacher_name']?.toString();
    _selectedSubjectCode = (item['code'] ?? item['subject_code'])?.toString();
    _selectedSubjectName = (item['name'] ?? item['subject_name'])?.toString();
    _selectedDept = item['department']?.toString();
    _selectedCourse = item['course']?.toString();
    _selectedSection = item['section']?.toString();
    _selectedSubjectLabel = "${_selectedSubjectCode ?? ''} - ${_selectedSubjectName ?? ''}";

    // When selecting a subject, ensure SUBJECT mode is active
    _attendanceMode = 'SUBJECT';

    // Clear previous scan session token cache so switching subjects allows immediate scanning
    _lastScannedToken = null;
    _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
    _isProcessing = false;
    _isScanningActive = true;
    debugPrint("SUBJECT_SWITCHED: Teacher=${ApiService().currentUser?['id']} Subject=$_selectedSubjectId ($_selectedSubjectName) Sem=$_selectedSemester");
  }

  @override
  void dispose() {
    _scannerController.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_isProcessing || !_isScanningActive || _isSheetOpen) return;

    final List<Barcode> barcodes = capture.barcodes;
    if (barcodes.isEmpty) return;

    final rawValue = barcodes.first.rawValue;
    if (rawValue == null || rawValue.isEmpty) return;

    final now = DateTime.now();
    // Scope debounce key strictly by mode + subject so switching modes or subjects allows immediate scanning of the same student
    final scanKey = _attendanceMode == 'GENERAL'
        ? "GENERAL_$rawValue"
        : "${_selectedSubjectId ?? 'sub'}_$rawValue";

    if (scanKey == _lastScannedToken &&
        now.difference(_lastScannedTime).inMilliseconds < 2000) {
      return;
    }

    _lastScannedToken = scanKey;
    _lastScannedTime = now;

    _processToken(rawValue);
  }

  void _completeSessionAndSwitchSubject() {
    setState(() {
      _lastScannedToken = null;
      _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
      _isProcessing = false;
      _isScanningActive = true;
    });
    if (_subjects.length > 1) {
      _showSubjectPickerBottomSheet();
    } else {
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("${_selectedSubjectCode ?? 'Subject'} session complete. Ready to continue."),
          duration: const Duration(seconds: 2),
          backgroundColor: const Color(0xFF10B981),
        ),
      );
    }
  }

  Future<void> _showSubjectPickerBottomSheet() async {
    if (_subjects.isEmpty) return;
    setState(() {
      _isSheetOpen = true;
      _isProcessing = false;
    });

    try {
      await showModalBottomSheet(
        context: context,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (ctx) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Icon(Icons.swap_horiz_rounded, color: Color(0xFF2563EB), size: 26),
                  const SizedBox(width: 10),
                  const Text(
                    "Select Next Subject",
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const Text(
                "Choose subject to switch context immediately with zero delay:",
                style: TextStyle(fontSize: 13, color: Colors.grey),
              ),
              const SizedBox(height: 12),
              ConstrainedBox(
                constraints: BoxConstraints(
                  maxHeight: MediaQuery.of(context).size.height * 0.45,
                ),
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: _subjects.length,
                  separatorBuilder: (context, index) => const Divider(height: 1),
                  itemBuilder: (context, idx) {
                    final sub = _subjects[idx];
                    final code = sub['code'] ?? sub['subject_code'] ?? '';
                    final name = sub['name'] ?? sub['subject_name'] ?? '';
                    final sem = sub['semester'] ?? '';
                    final isCurrent = idx == _selectedSubjectIndex;

                    return ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      leading: CircleAvatar(
                        backgroundColor: isCurrent ? const Color(0xFF10B981) : const Color(0xFF2563EB).withValues(alpha: 0.1),
                        child: Icon(
                          isCurrent ? Icons.check : Icons.book,
                          color: isCurrent ? Colors.white : const Color(0xFF2563EB),
                          size: 20,
                        ),
                      ),
                      title: Text(
                        "[$code] $name",
                        style: TextStyle(
                          fontWeight: isCurrent ? FontWeight.bold : FontWeight.w600,
                          fontSize: 14,
                          color: isCurrent ? const Color(0xFF10B981) : Colors.black87,
                        ),
                      ),
                      subtitle: Text(
                        sem.isNotEmpty ? "Semester: $sem" : "General",
                        style: const TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                      trailing: isCurrent
                          ? const Chip(
                              label: Text("Active", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF047857))),
                              backgroundColor: Color(0xFFD1FAE5),
                              padding: EdgeInsets.zero,
                            )
                          : const Icon(Icons.chevron_right, color: Colors.grey),
                      onTap: () {
                        Navigator.pop(ctx);
                        setState(() {
                          _selectSubjectAtIndex(idx);
                        });
                        ScaffoldMessenger.of(context).hideCurrentSnackBar();
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text("Switched to [$code] $name ($sem). Ready to scan."),
                            duration: const Duration(seconds: 2),
                            backgroundColor: const Color(0xFF10B981),
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSheetOpen = false;
          _isProcessing = false;
          _lastScannedToken = null;
          _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
        });
      }
    }
  }

  Future<void> _processToken(String token) async {
    if (_isProcessing || _isSheetOpen) return;

    // Capture context based on active attendance mode (GENERAL vs SUBJECT)
    final isGeneral = _attendanceMode == 'GENERAL';
    final currentSubId = isGeneral ? null : _selectedSubjectId;
    final currentSubCode = isGeneral ? 'GENERAL' : _selectedSubjectCode;
    final currentSubName = isGeneral ? 'General Daily Attendance' : _selectedSubjectName;
    final currentSem = isGeneral ? null : _selectedSemester;
    final currentLabel = isGeneral
        ? (_coordinatorAssignments.isNotEmpty ? _coordinatorAssignments[0]['class_label'] : 'General Attendance')
        : _selectedSubjectLabel;

    setState(() {
      _isProcessing = true;
    });

    HapticFeedback.mediumImpact();

    debugPrint("ATTENDANCE_SCAN_REQUEST: Mode=$_attendanceMode Teacher=${ApiService().currentUser?['id']} Subject=$currentSubId [$currentSubCode - $currentSubName] Sem=$currentSem Token=$token");

    Map<String, dynamic> result;
    try {
      result = await ApiService().scanAttendance(
        token,
        subjectId: currentSubId,
        semester: currentSem,
        attendanceType: _attendanceMode,
      );
    } catch (e) {
      debugPrint("ATTENDANCE_SCAN_EXCEPTION: $e");
      result = {
        'success': false,
        'action': 'NETWORK_ERROR',
        'message': 'Failed to mark attendance: $e',
      };
    } finally {
      if (mounted) {
        setState(() {
          _isProcessing = false;
        });
      }
    }

    debugPrint("ATTENDANCE_SCAN_RESPONSE: Success=${result['success']} Action=${result['action']} RecordId=${result['attendance']?['id']}");

    if (!mounted) return;

    if (result['success'] == true) {
      HapticFeedback.heavyImpact();
      final student = result['student'] is Map ? Map<String, dynamic>.from(result['student']) : <String, dynamic>{};
      final attendance = result['attendance'] is Map ? Map<String, dynamic>.from(result['attendance']) : <String, dynamic>{};

      setState(() {
        _sessionScans.insert(0, {
          'name': student['full_name'] ?? 'Student',
          'id': student['student_id'] ?? '-',
          'action': result['action'] ?? 'TIME_IN',
          'time': attendance['time_in'] ?? attendance['time_out'] ?? 'Just now',
          'subject': currentLabel ?? 'General',
          'semester': currentSem ?? '',
          'success': true,
        });
      });

      await _showScanFeedbackSheet(
        isSuccess: true,
        title: result['action'] == 'TIME_IN' ? 'TIME IN RECORDED' : 'TIME OUT RECORDED',
        message: result['message'] ?? 'Attendance marked successfully.',
        action: result['action'] ?? 'TIME_IN',
        student: student,
        attendance: attendance,
        subject: result['subject'] is Map ? Map<String, dynamic>.from(result['subject']) : null,
        subjectLabel: currentLabel,
      );
    } else {
      HapticFeedback.vibrate();
      final student = result['student'] is Map ? Map<String, dynamic>.from(result['student']) : <String, dynamic>{};
      await _showScanFeedbackSheet(
        isSuccess: false,
        title: result['action'] ?? 'SCAN ALERT',
        message: result['message'] ?? 'Unable to process QR code.',
        action: result['action'] ?? 'FAILED',
        student: student,
        attendance: result['attendance'] is Map ? Map<String, dynamic>.from(result['attendance']) : null,
        subject: result['subject'] is Map ? Map<String, dynamic>.from(result['subject']) : null,
        subjectLabel: currentLabel,
      );
    }
  }

  Future<void> _showManualEntryDialog() async {
    final controller = TextEditingController();
    bool searching = false;
    String status = "";

    setState(() {
      _isSheetOpen = true;
      _isProcessing = false;
    });

    try {
      await showDialog(
        context: context,
        builder: (ctx) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Row(
              children: [
                Icon(Icons.keyboard, color: Colors.blue),
                SizedBox(width: 8),
                Text("Manual Student ID"),
              ],
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  "Enter student roll number or ID to mark attendance:",
                  style: TextStyle(fontSize: 13),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: controller,
                  autofocus: true,
                  decoration: const InputDecoration(
                    labelText: "Student ID or Roll No",
                    hintText: "e.g. STU2026001 or CS-2024-042",
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.badge_outlined),
                  ),
                ),
                if (status.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(
                    status,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: status.startsWith("✓") ? Colors.green : Colors.orange,
                    ),
                  ),
                ],
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text("Cancel"),
              ),
              ElevatedButton(
                onPressed: searching
                    ? null
                    : () async {
                        final q = controller.text.trim();
                        if (q.isEmpty) return;

                        setDialogState(() {
                          searching = true;
                          status = "Looking up student...";
                        });

                        final nav = Navigator.of(ctx);
                        final students = await ApiService().searchStudents(q);
                        if (students.isNotEmpty) {
                          final student = students.first;
                          final token = student['student_id'];
                          nav.pop();
                          _processToken(token);
                        } else {
                          setDialogState(() {
                            searching = false;
                            status = "No student found with that ID.";
                          });
                        }
                      },
                child: searching
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text("Verify & Mark"),
              ),
            ],
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSheetOpen = false;
          _isProcessing = false;
          _lastScannedToken = null;
          _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
        });
      }
    }
  }

  Future<void> _showScanFeedbackSheet({
    required bool isSuccess,
    required String title,
    required String message,
    required String action,
    required Map<String, dynamic> student,
    Map<String, dynamic>? attendance,
    Map<String, dynamic>? subject,
    String? subjectLabel,
  }) async {
    setState(() {
      _isSheetOpen = true;
      _isProcessing = false;
    });

    final color = isSuccess
        ? (action == 'TIME_IN' ? const Color(0xFF10B981) : const Color(0xFF3B82F6))
        : const Color(0xFFF59E0B);

    final subName = subject?['name'] ?? _selectedSubjectName ?? 'Subject';
    final subCode = subject?['code'] ?? _selectedSubjectCode ?? '';
    final subSem = subject?['semester'] ?? _selectedSemester ?? '';
    final timeStr = attendance?['time_in'] ?? attendance?['time_out'] ?? 'Just now';
    final statusStr = attendance?['status'] ?? (action == 'TIME_IN' ? 'Present' : action);

    try {
      await showModalBottomSheet(
        context: context,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (ctx) => Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      isSuccess ? Icons.check_circle : Icons.warning_amber_rounded,
                      color: color,
                      size: 32,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: color,
                          ),
                        ),
                        Text(
                          message,
                          style: const TextStyle(fontSize: 13),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              if (student.isNotEmpty) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
                  ),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 20,
                            backgroundColor: Theme.of(context).colorScheme.primary,
                            child: Text(
                              (student['full_name'] ?? 'S')[0].toUpperCase(),
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  student['full_name'] ?? 'Student Name',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14,
                                  ),
                                ),
                                Text(
                                  "ID: ${student['student_id']} • Roll: ${student['roll_number'] ?? '-'}",
                                  style: const TextStyle(fontSize: 12, color: Colors.grey),
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
                              statusStr,
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                                color: color,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const Divider(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Row(
                              children: [
                                const Icon(Icons.menu_book, size: 14, color: Color(0xFF2563EB)),
                                const SizedBox(width: 4),
                                Expanded(
                                  child: Text(
                                    "[$subCode] $subName (${subSem.isNotEmpty ? subSem : 'General'})",
                                    style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Color(0xFF2563EB)),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Row(
                            children: [
                              const Icon(Icons.access_time, size: 14, color: Colors.grey),
                              const SizedBox(width: 4),
                              Text(
                                timeStr,
                                style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.black87),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => Navigator.pop(ctx),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: color,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text("Continue Scanning"),
                    ),
                  ),
                  if (_subjects.length > 1) ...[
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () {
                          Navigator.pop(ctx);
                          WidgetsBinding.instance.addPostFrameCallback((_) {
                            if (mounted) _showSubjectPickerBottomSheet();
                          });
                        },
                        icon: const Icon(Icons.swap_horiz_rounded, size: 16),
                        label: const Text("Switch Subject"),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSheetOpen = false;
          _isProcessing = false;
          _lastScannedToken = null;
          _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Camera QR Scanner"),
        actions: [
          IconButton(
            icon: const Icon(Icons.keyboard),
            tooltip: "Manual ID Entry",
            onPressed: _showManualEntryDialog,
          ),
          IconButton(
            icon: const Icon(Icons.flash_on),
            tooltip: "Toggle Torch",
            onPressed: () => _scannerController.toggleTorch(),
          ),
          IconButton(
            icon: const Icon(Icons.cameraswitch),
            tooltip: "Switch Camera",
            onPressed: () => _scannerController.switchCamera(),
          ),
        ],
      ),
      body: _loadingSubjects
          ? const Center(child: CircularProgressIndicator())
          : (_subjects.isEmpty && _coordinatorAssignments.isEmpty)
              ? Center(
                  child: Container(
                    margin: const EdgeInsets.all(24),
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.amber.shade300, width: 1.5),
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.warning_amber_rounded, size: 54, color: Colors.amber.shade700),
                        const SizedBox(height: 16),
                        const Text(
                          "No Subject or Class Assigned",
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          "No academic subjects or class coordinator assignments have been linked to your account.\nPlease contact the administrator.",
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 14, color: Colors.grey),
                        ),
                      ],
                    ),
                  ),
                )
              : Column(
                  children: [
                    // ATTENDANCE MODE SWITCHER (General vs Subject)
                    if (_coordinatorAssignments.isNotEmpty)
                      Container(
                        margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
                        decoration: BoxDecoration(
                          color: Colors.grey.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        padding: const EdgeInsets.all(3),
                        child: Row(
                          children: [
                            Expanded(
                              child: GestureDetector(
                                onTap: () {
                                  if (_attendanceMode != 'GENERAL') {
                                    setState(() {
                                      _attendanceMode = 'GENERAL';
                                      _lastScannedToken = null;
                                      _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
                                    });
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                        content: Text("Switched to General Attendance. Ready to scan."),
                                        duration: Duration(seconds: 2),
                                        behavior: SnackBarBehavior.floating,
                                      ),
                                    );
                                  }
                                },
                                child: Container(
                                  padding: const EdgeInsets.symmetric(vertical: 8),
                                  decoration: BoxDecoration(
                                    color: _attendanceMode == 'GENERAL' ? const Color(0xFF2563EB) : Colors.transparent,
                                    borderRadius: BorderRadius.circular(8),
                                    boxShadow: _attendanceMode == 'GENERAL'
                                        ? [
                                            BoxShadow(
                                              color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                                              blurRadius: 4,
                                              offset: const Offset(0, 2),
                                            ),
                                          ]
                                        : null,
                                  ),
                                  child: Center(
                                    child: Text(
                                      "General Attendance",
                                      style: TextStyle(
                                        color: _attendanceMode == 'GENERAL' ? Colors.white : Colors.grey.shade700,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 12,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                            Expanded(
                              child: GestureDetector(
                                onTap: () {
                                  if (_subjects.isEmpty) {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                        content: Text("No academic subjects assigned to your faculty profile."),
                                        duration: Duration(seconds: 2),
                                        behavior: SnackBarBehavior.floating,
                                      ),
                                    );
                                    return;
                                  }
                                  if (_attendanceMode != 'SUBJECT') {
                                    setState(() {
                                      _attendanceMode = 'SUBJECT';
                                      _lastScannedToken = null;
                                      _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
                                    });
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(
                                        content: Text("Switched to [${_selectedSubjectCode ?? ''}] ${_selectedSubjectName ?? ''}. Ready to scan."),
                                        duration: const Duration(seconds: 2),
                                        behavior: SnackBarBehavior.floating,
                                      ),
                                    );
                                  }
                                },
                                child: Container(
                                  padding: const EdgeInsets.symmetric(vertical: 8),
                                  decoration: BoxDecoration(
                                    color: _attendanceMode == 'SUBJECT' ? const Color(0xFF2563EB) : Colors.transparent,
                                    borderRadius: BorderRadius.circular(8),
                                    boxShadow: _attendanceMode == 'SUBJECT'
                                        ? [
                                            BoxShadow(
                                              color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                                              blurRadius: 4,
                                              offset: const Offset(0, 2),
                                            ),
                                          ]
                                        : null,
                                  ),
                                  child: Center(
                                    child: Text(
                                      "Subject Attendance",
                                      style: TextStyle(
                                        color: _attendanceMode == 'SUBJECT' ? Colors.white : Colors.grey.shade700,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 12,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),

                    // GENERAL ATTENDANCE CARD
                    if (_attendanceMode == 'GENERAL')
                      Container(
                        margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEFF6FF),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: const Color(0xFF2563EB).withValues(alpha: 0.4)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF2563EB),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: const Text(
                                    'GENERAL ATTENDANCE',
                                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 11),
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(color: const Color(0xFF2563EB).withValues(alpha: 0.3)),
                                  ),
                                  child: Text(
                                    _coordinatorAssignments.isNotEmpty
                                        ? (_coordinatorAssignments[0]['semester'] ?? 'General')
                                        : 'Daily',
                                    style: const TextStyle(color: Color(0xFF2563EB), fontWeight: FontWeight.bold, fontSize: 11),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Text(
                              _coordinatorAssignments.isNotEmpty
                                  ? (_coordinatorAssignments[0]['class_label'] ?? 'Class Coordinator Attendance')
                                  : 'General Daily Attendance',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF1E3A8A)),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              "Coordinator: ${ApiService().currentUser?['full_name'] ?? 'Faculty'}",
                              style: TextStyle(fontSize: 12, color: Colors.blue.shade900, fontWeight: FontWeight.w500),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              "Student attendance counts once per day. Does not duplicate with subject attendances.",
                              style: TextStyle(fontSize: 11, color: Colors.blue.shade700),
                            ),
                          ],
                        ),
                      )
                    // SUBJECT SELECTION / DETAILS HEADER
                    else if (_subjects.length == 1)
                      // RULE 1: Exactly 1 assigned subject -> Hide dropdown, display assignment card directly
                      Container(
                        margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.surface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: const Color(0xFF2563EB).withValues(alpha: 0.3)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF2563EB),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    _selectedSubjectCode ?? 'SUBJECT',
                                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 11),
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.blue.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    _selectedSemester ?? 'General Sem',
                                    style: const TextStyle(color: Color(0xFF2563EB), fontWeight: FontWeight.bold, fontSize: 11),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Text(
                              _selectedSubjectName ?? '',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              "Teacher: ${_selectedTeacherName ?? (ApiService().currentUser?['full_name'] ?? 'Teacher')}",
                              style: TextStyle(fontSize: 12, color: Colors.grey.shade700, fontWeight: FontWeight.w500),
                            ),
                            if (_selectedDept != null || _selectedCourse != null) ...[
                              const SizedBox(height: 2),
                              Text(
                                "${_selectedDept ?? ''} ${_selectedCourse != null ? '• $_selectedCourse' : ''} ${_selectedSection != null && _selectedSection!.isNotEmpty ? '• Sec $_selectedSection' : ''}",
                                style: const TextStyle(fontSize: 11, color: Colors.grey),
                              ),
                            ],
                          ],
                        ),
                      )
                    else
                      // RULE 2: Multiple assigned subjects -> Show selector with lock during active session
                      Container(
                        margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.surface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.grey.withValues(alpha: 0.25)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  "Select Subject",
                                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.grey),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF10B981).withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(color: const Color(0xFF10B981), width: 0.8),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Container(
                                        width: 6,
                                        height: 6,
                                        decoration: const BoxDecoration(
                                          color: Color(0xFF10B981),
                                          shape: BoxShape.circle,
                                        ),
                                      ),
                                      const SizedBox(width: 4),
                                      const Text(
                                        "Live Ready",
                                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF047857)),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 4),
                            DropdownButtonHideUnderline(
                              child: DropdownButton<int>(
                                value: _selectedSubjectIndex,
                                isExpanded: true,
                                items: _subjects.asMap().entries.map((entry) {
                                  final idx = entry.key;
                                  final sub = entry.value;
                                  final code = sub['code'] ?? sub['subject_code'] ?? '';
                                  final name = sub['name'] ?? sub['subject_name'] ?? '';
                                  final sem = sub['semester'] ?? '';
                                  return DropdownMenuItem<int>(
                                    value: idx,
                                    child: Text(
                                      "[$code] $name — $sem",
                                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  );
                                }).toList(),
                                onChanged: (idx) {
                                  if (idx != null) {
                                    setState(() {
                                      _selectSubjectAtIndex(idx);
                                    });
                                    ScaffoldMessenger.of(context).hideCurrentSnackBar();
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(
                                        content: Text("Switched to [${_selectedSubjectCode ?? ''}] ${_selectedSubjectName ?? ''}. Ready to scan."),
                                        duration: const Duration(seconds: 2),
                                        backgroundColor: const Color(0xFF10B981),
                                      ),
                                    );
                                  }
                                },
                              ),
                            ),
                            const Divider(height: 10),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  "Teacher: ${_selectedTeacherName ?? (ApiService().currentUser?['full_name'] ?? 'Teacher')}",
                                  style: TextStyle(fontSize: 11, color: Colors.grey.shade700, fontWeight: FontWeight.w500),
                                ),
                                Text(
                                  "Sem: ${_selectedSemester ?? '-'}",
                                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF2563EB)),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),

                    // START / SWITCH ATTENDANCE ACTION BUTTON
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                      child: SizedBox(
                        width: double.infinity,
                        child: ElevatedButton.icon(
                          onPressed: () {
                            if (_subjects.length > 1) {
                              _completeSessionAndSwitchSubject();
                            } else {
                              setState(() {
                                _isScanningActive = true;
                                _lastScannedToken = null;
                                _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
                              });
                              ScaffoldMessenger.of(context).hideCurrentSnackBar();
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text("${_selectedSubjectCode ?? 'Subject'} scanner active and ready."),
                                  duration: const Duration(seconds: 2),
                                  backgroundColor: const Color(0xFF10B981),
                                ),
                              );
                            }
                          },
                          icon: Icon(
                            _subjects.length > 1 ? Icons.swap_horiz_rounded : Icons.check_circle_rounded,
                            size: 20,
                          ),
                          label: Text(
                            _subjects.length > 1
                                ? "Switch Subject (${_selectedSubjectCode ?? ''})"
                                : "${_selectedSubjectCode ?? 'Subject'} Active",
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF2563EB),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 11),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      ),
                    ),

                    // Scanner Viewport Box
                    Expanded(
                      flex: 5,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          MobileScanner(
                            controller: _scannerController,
                            onDetect: _onDetect,
                          ),

                          // Viewport Scan Frame
                          Container(
                            width: 240,
                            height: 240,
                            decoration: BoxDecoration(
                              border: Border.all(
                                color: _isProcessing
                                    ? Colors.amber
                                    : (_isScanningActive ? Colors.blueAccent : Colors.grey.shade600),
                                width: 3,
                              ),
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),

                          if (!_isScanningActive)
                            Container(
                              color: Colors.black.withValues(alpha: 0.75),
                              child: Center(
                                child: Padding(
                                  padding: const EdgeInsets.all(20),
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(Icons.qr_code_scanner, size: 44, color: Colors.white.withValues(alpha: 0.8)),
                                      const SizedBox(height: 10),
                                      const Text(
                                        "Attendance Session Inactive",
                                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                                      ),
                                      const SizedBox(height: 4),
                                      const Text(
                                        "Tap [ Start Attendance ] to lock subject and scan student QR codes",
                                        textAlign: TextAlign.center,
                                        style: TextStyle(color: Colors.white70, fontSize: 12),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),

                          if (_isProcessing)
                            Container(
                              color: Colors.black45,
                              child: const Center(
                                child: CircularProgressIndicator(color: Colors.white),
                              ),
                            ),

                          if (_isScanningActive)
                            Positioned(
                              bottom: 12,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                                decoration: BoxDecoration(
                                  color: Colors.black54,
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: const Text(
                                  "Center student QR code in frame",
                                  style: TextStyle(color: Colors.white, fontSize: 12),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),

                    // Session Feed List
          Expanded(
            flex: 4,
            child: Container(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        "Session Scans",
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Chip(
                        label: Text("${_sessionScans.length} Scanned"),
                        visualDensity: VisualDensity.compact,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  Expanded(
                    child: _sessionScans.isEmpty
                        ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.qr_code_2, size: 48, color: Colors.grey.withValues(alpha: 0.5)),
                                const SizedBox(height: 8),
                                const Text(
                                  "No scans in this session yet",
                                  style: TextStyle(color: Colors.grey, fontSize: 13),
                                ),
                              ],
                            ),
                          )
                        : ListView.separated(
                            itemCount: _sessionScans.length,
                            separatorBuilder: (_, _) => const Divider(height: 1),
                            itemBuilder: (ctx, i) {
                              final item = _sessionScans[i];
                              final isTimeIn = item['action'] == 'TIME_IN';
                              final subject = item['subject'] ?? 'General';
                              return ListTile(
                                leading: CircleAvatar(
                                  backgroundColor: isTimeIn ? Colors.green : Colors.blue,
                                  foregroundColor: Colors.white,
                                  child: Icon(isTimeIn ? Icons.login : Icons.logout, size: 20),
                                ),
                                title: Text(item['name'], style: const TextStyle(fontWeight: FontWeight.bold)),
                                subtitle: Text("${item['id']} • ${item['time']}\n[$subject]"),
                                isThreeLine: true,
                                trailing: Text(
                                  item['action'],
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 12,
                                    color: isTimeIn ? Colors.green : Colors.blue,
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
