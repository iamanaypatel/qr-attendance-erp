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
  String? _lastScannedToken;
  DateTime _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
  final List<Map<String, dynamic>> _sessionScans = [];

  List<Map<String, dynamic>> _subjects = [];
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
  bool _isScanningActive = false;

  @override
  void initState() {
    super.initState();
    _fetchSubjects();
  }

  Future<void> _fetchSubjects() async {
    final user = ApiService().currentUser;
    List<dynamic> list = [];
    if (user != null && user['role'] == 'teacher') {
      list = await ApiService().getTeacherSubjects();
    } else {
      list = await ApiService().getSubjects();
    }

    if (mounted) {
      setState(() {
        _subjects = list.map((e) => Map<String, dynamic>.from(e)).toList();
        _loadingSubjects = false;
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
    _selectedSubjectId = item['subject_id'] ?? item['id'] as int?;
    _selectedSemester = item['semester'] as String?;
    _selectedTeacherName = item['teacher_name'] as String?;
    _selectedSubjectCode = item['code'] ?? item['subject_code'] as String?;
    _selectedSubjectName = item['name'] ?? item['subject_name'] as String?;
    _selectedDept = item['department'] as String?;
    _selectedCourse = item['course'] as String?;
    _selectedSection = item['section'] as String?;
    _selectedSubjectLabel = "${_selectedSubjectCode ?? ''} - ${_selectedSubjectName ?? ''}";

    // Clear previous scan session token cache so switching subjects allows immediate scanning
    _lastScannedToken = null;
    _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
    debugPrint("SUBJECT_SWITCHED: Teacher=${ApiService().currentUser?['id']} Subject=$_selectedSubjectId ($_selectedSubjectName) Sem=$_selectedSemester");
  }

  @override
  void dispose() {
    _scannerController.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_isProcessing || !_isScanningActive) return;

    final List<Barcode> barcodes = capture.barcodes;
    if (barcodes.isEmpty) return;

    final rawValue = barcodes.first.rawValue;
    if (rawValue == null || rawValue.isEmpty) return;

    final now = DateTime.now();
    // Debounce identical scans within 3 seconds
    if (rawValue == _lastScannedToken &&
        now.difference(_lastScannedTime).inSeconds < 3) {
      return;
    }

    _lastScannedToken = rawValue;
    _lastScannedTime = now;

    _processToken(rawValue);
  }

  Future<void> _processToken(String token) async {
    setState(() {
      _isProcessing = true;
    });

    HapticFeedback.mediumImpact();

    debugPrint("ATTENDANCE_SCAN_REQUEST: Teacher=${ApiService().currentUser?['id']} Subject=$_selectedSubjectId ($_selectedSubjectName) Sem=$_selectedSemester Token=$token");

    final result = await ApiService().scanAttendance(
      token,
      subjectId: _selectedSubjectId,
      semester: _selectedSemester,
    );

    debugPrint("ATTENDANCE_SCAN_RESPONSE: Success=${result['success']} Action=${result['action']} RecordId=${result['attendance']?['id']}");

    if (!mounted) return;

    setState(() {
      _isProcessing = false;
    });

    if (result['success'] == true) {
      HapticFeedback.heavyImpact();
      final student = result['student'] ?? {};
      final attendance = result['attendance'] ?? {};

      setState(() {
        _sessionScans.insert(0, {
          'name': student['full_name'] ?? 'Student',
          'id': student['student_id'] ?? '-',
          'action': result['action'] ?? 'TIME_IN',
          'time': attendance['time_in'] ?? attendance['time_out'] ?? 'Just now',
          'subject': _selectedSubjectLabel ?? 'General',
          'semester': _selectedSemester ?? '',
          'success': true,
        });
      });

      _showScanFeedbackSheet(
        isSuccess: true,
        title: result['action'] == 'TIME_IN' ? 'TIME IN RECORDED' : 'TIME OUT RECORDED',
        message: result['message'] ?? 'Attendance marked successfully.',
        action: result['action'] ?? 'TIME_IN',
        student: student,
        subjectLabel: _selectedSubjectLabel,
      );
    } else {
      HapticFeedback.vibrate();
      final student = result['student'] ?? {};
      _showScanFeedbackSheet(
        isSuccess: false,
        title: result['action'] ?? 'SCAN ALERT',
        message: result['message'] ?? 'Unable to process QR code.',
        action: result['action'] ?? 'FAILED',
        student: student,
        subjectLabel: _selectedSubjectLabel,
      );
    }
  }

  void _showManualEntryDialog() {
    final controller = TextEditingController();
    bool searching = false;
    String status = "";

    showDialog(
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
  }

  void _showScanFeedbackSheet({
    required bool isSuccess,
    required String title,
    required String message,
    required String action,
    required Map<String, dynamic> student,
    String? subjectLabel,
  }) {
    final color = isSuccess
        ? (action == 'TIME_IN' ? const Color(0xFF10B981) : const Color(0xFF3B82F6))
        : const Color(0xFFF59E0B);

    showModalBottomSheet(
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
                      if (subjectLabel != null) ...[
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.blue.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            "Subject: $subjectLabel",
                            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.blue),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            if (student.isNotEmpty) ...[
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
                ),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 24,
                      backgroundColor: Theme.of(context).colorScheme.primary,
                      child: Text(
                        (student['full_name'] ?? 'S')[0].toUpperCase(),
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            student['full_name'] ?? 'Student Name',
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 15,
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
                        action,
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                          color: color,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
            ],

            ElevatedButton(
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
          ],
        ),
      ),
    );
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
          : _subjects.isEmpty
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
                          "No Subject Assigned",
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          "No subject has been assigned to your account.\nPlease contact the administrator.",
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 14, color: Colors.grey),
                        ),
                      ],
                    ),
                  ),
                )
              : Column(
                  children: [
                    // SUBJECT SELECTION / DETAILS HEADER
                    if (_subjects.length == 1)
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
                                if (_isScanningActive)
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: Colors.amber.withValues(alpha: 0.2),
                                      borderRadius: BorderRadius.circular(6),
                                      border: Border.all(color: Colors.amber.shade600, width: 0.8),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.lock, size: 12, color: Colors.amber.shade900),
                                        const SizedBox(width: 4),
                                        Text(
                                          "Session Locked",
                                          style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.amber.shade900),
                                        ),
                                      ],
                                    ),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 4),
                            if (_isScanningActive)
                              Container(
                                width: double.infinity,
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                decoration: BoxDecoration(
                                  color: Colors.grey.withValues(alpha: 0.08),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  "${_selectedSubjectCode ?? ''} - ${_selectedSubjectName ?? ''} (${_selectedSemester ?? ''})",
                                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                ),
                              )
                            else
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

                    // START / STOP ATTENDANCE ACTION BUTTON
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                      child: SizedBox(
                        width: double.infinity,
                        child: ElevatedButton.icon(
                          onPressed: () {
                            setState(() {
                              _isScanningActive = !_isScanningActive;
                              _lastScannedToken = null;
                              _lastScannedTime = DateTime.now().subtract(const Duration(seconds: 10));
                            });
                          },
                          icon: Icon(_isScanningActive ? Icons.stop_circle : Icons.play_circle_fill, size: 20),
                          label: Text(
                            _isScanningActive ? "Stop Attendance (Finish Session)" : "Start Attendance",
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: _isScanningActive ? Colors.red.shade600 : const Color(0xFF2563EB),
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
