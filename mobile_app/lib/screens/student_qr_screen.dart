import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:mobile_app/services/api_service.dart';

class StudentQrScreen extends StatefulWidget {
  const StudentQrScreen({super.key});

  @override
  State<StudentQrScreen> createState() => _StudentQrScreenState();
}

class _StudentQrScreenState extends State<StudentQrScreen> {
  String _studentToken = "STU2026001";
  String _studentName = "Aarav Sharma";
  String _studentId = "STU2026001";
  String _rollNumber = "CS-2024-042";
  String _department = "Computer Science & Engineering";
  String _course = "B.Tech Computer Science";
  String _semester = "4th Semester";
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _fetchDefaultStudent();
  }

  Future<void> _fetchDefaultStudent() async {
    setState(() {
      _isLoading = true;
    });

    final students = await ApiService().searchStudents("");
    if (students.isNotEmpty) {
      final s = students.first;
      setState(() {
        _studentToken = s['student_id'] ?? 'STU2026001';
        _studentName = s['full_name'] ?? 'Aarav Sharma';
        _studentId = s['student_id'] ?? 'STU2026001';
        _rollNumber = s['roll_number'] ?? 'CS-2024-042';
        _department = s['department_code'] ?? 'CSE';
        _course = s['course'] ?? 'B.Tech';
        _semester = "${s['semester'] ?? 4}th Semester";
      });
    }

    setState(() {
      _isLoading = false;
    });
  }

  void _showStudentPicker() async {
    final students = await ApiService().searchStudents("");
    if (!mounted) return;

    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Select Student Card",
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.builder(
                itemCount: students.length,
                itemBuilder: (context, i) {
                  final s = students[i];
                  return ListTile(
                    leading: CircleAvatar(
                      child: Text((s['full_name'] ?? 'S')[0]),
                    ),
                    title: Text(s['full_name'] ?? 'Student'),
                    subtitle: Text("${s['student_id']} • ${s['roll_number']}"),
                    onTap: () {
                      setState(() {
                        _studentToken = s['student_id'] ?? 'STU2026001';
                        _studentName = s['full_name'] ?? 'Student';
                        _studentId = s['student_id'] ?? 'STU2026001';
                        _rollNumber = s['roll_number'] ?? '-';
                        _department = s['department_code'] ?? 'General';
                        _course = s['course'] ?? '-';
                        _semester = "${s['semester'] ?? 1}th Sem";
                      });
                      Navigator.pop(ctx);
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Digital Student ID & QR"),
        actions: [
          IconButton(
            icon: const Icon(Icons.people_outline),
            tooltip: "Switch Student Card",
            onPressed: _showStudentPicker,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  // Vector Digital ID Card
                  Container(
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF1E293B) : Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.15),
                          blurRadius: 20,
                          offset: const Offset(0, 8),
                        ),
                      ],
                      border: Border.all(
                        color: Colors.blue.withValues(alpha: 0.3),
                        width: 1.5,
                      ),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: Column(
                      children: [
                        // Card Header Banner
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 12),
                          decoration: const BoxDecoration(
                            gradient: LinearGradient(
                              colors: [Color(0xFF1E3A8A), Color(0xFF2563EB)],
                            ),
                          ),
                          child: const Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    "APEX INSTITUTE OF TECHNOLOGY",
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 13,
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                  Text(
                                    "OFFICIAL STUDENT IDENTITY PASS",
                                    style: TextStyle(
                                      color: Colors.white70,
                                      fontSize: 10,
                                      letterSpacing: 0.8,
                                    ),
                                  ),
                                ],
                              ),
                              Icon(Icons.school, color: Colors.white, size: 24),
                            ],
                          ),
                        ),

                        // Card Body
                        Padding(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            children: [
                              // Avatar & Name
                              CircleAvatar(
                                radius: 36,
                                backgroundColor:
                                    Theme.of(context).colorScheme.primary,
                                child: Text(
                                  _studentName.isNotEmpty
                                      ? _studentName[0].toUpperCase()
                                      : 'S',
                                  style: const TextStyle(
                                    fontSize: 32,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 12),
                              Text(
                                _studentName,
                                style: const TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Container(
                                margin: const EdgeInsets.only(top: 4),
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.blue.withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  "ID: $_studentId",
                                  style: const TextStyle(
                                    color: Colors.blue,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 16),

                              // High Res QR Code Display
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(16),
                                  border: Border.all(color: Colors.grey.shade300),
                                ),
                                child: QrImageView(
                                  data: _studentToken,
                                  version: QrVersions.auto,
                                  size: 180,
                                  backgroundColor: Colors.white,
                                ),
                              ),
                              const SizedBox(height: 16),

                              // Academic Details Grid
                              Row(
                                children: [
                                  Expanded(
                                    child: _buildDetailField(
                                        "ROLL NO", _rollNumber),
                                  ),
                                  Expanded(
                                    child: _buildDetailField(
                                        "DEPARTMENT", _department),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Row(
                                children: [
                                  Expanded(
                                    child: _buildDetailField("COURSE", _course),
                                  ),
                                  Expanded(
                                    child: _buildDetailField(
                                        "SEMESTER", _semester),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),

                        // Card Footer
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          color: const Color(0xFF1E3A8A),
                          alignment: Alignment.center,
                          child: const Text(
                            "SCAN UPON ARRIVAL & DEPARTURE • VERIFIED CREDENTIAL",
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 9,
                              letterSpacing: 0.5,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 20),
                  ElevatedButton.icon(
                    onPressed: _showStudentPicker,
                    icon: const Icon(Icons.swap_horiz),
                    label: const Text("Switch / Select Another Student"),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildDetailField(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.bold,
            color: Colors.grey,
            letterSpacing: 0.5,
          ),
        ),
        Text(
          value,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }
}
