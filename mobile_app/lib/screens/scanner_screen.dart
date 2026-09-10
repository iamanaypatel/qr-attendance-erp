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
  String? _selectedSubjectLabel;
  bool _loadingSubjects = true;

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
          _selectedSubjectId = _subjects.first['id'] as int?;
          _selectedSubjectLabel = "${_subjects.first['subject_code']} - ${_subjects.first['subject_name']}";
        }
      });
    }
  }

  @override
  void dispose() {
    _scannerController.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_isProcessing) return;

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

    final result = await ApiService().scanAttendance(token, subjectId: _selectedSubjectId);

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
      body: Column(
        children: [
          // Subject Selector Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border(
                bottom: BorderSide(color: Colors.grey.withValues(alpha: 0.2)),
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.book_outlined, size: 20, color: Color(0xFF2563EB)),
                const SizedBox(width: 8),
                const Text(
                  "Subject:",
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _loadingSubjects
                      ? const Align(
                          alignment: Alignment.centerLeft,
                          child: SizedBox(
                            height: 16,
                            width: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        )
                      : DropdownButtonHideUnderline(
                          child: DropdownButton<int?>(
                            value: _selectedSubjectId,
                            isExpanded: true,
                            hint: const Text("General (No Subject)", style: TextStyle(fontSize: 13)),
                            items: [
                              const DropdownMenuItem<int?>(
                                value: null,
                                child: Text("General / No Subject", style: TextStyle(fontSize: 13)),
                              ),
                              ..._subjects.map((sub) => DropdownMenuItem<int?>(
                                    value: sub['id'] as int?,
                                    child: Text(
                                      "${sub['subject_code']} - ${sub['subject_name']}",
                                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  )),
                            ],
                            onChanged: (val) {
                              setState(() {
                                _selectedSubjectId = val;
                                if (val != null) {
                                  final found = _subjects.firstWhere((s) => s['id'] == val, orElse: () => {});
                                  _selectedSubjectLabel = "${found['subject_code']} - ${found['subject_name']}";
                                } else {
                                  _selectedSubjectLabel = null;
                                }
                              });
                            },
                          ),
                        ),
                ),
              ],
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
                  width: 250,
                  height: 250,
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: _isProcessing ? Colors.amber : Colors.blueAccent,
                      width: 3,
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),

                if (_isProcessing)
                  Container(
                    color: Colors.black45,
                    child: const Center(
                      child: CircularProgressIndicator(color: Colors.white),
                    ),
                  ),

                Positioned(
                  bottom: 16,
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
