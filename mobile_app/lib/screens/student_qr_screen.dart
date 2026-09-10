import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:mobile_app/services/api_service.dart';

class StudentQrScreen extends StatefulWidget {
  const StudentQrScreen({super.key});

  @override
  State<StudentQrScreen> createState() => _StudentQrScreenState();
}

class _StudentQrScreenState extends State<StudentQrScreen> {
  String _studentToken = "";
  String _studentName = "";
  String _studentId = "";
  String _rollNumber = "";
  String _department = "";
  String _course = "";
  String _semester = "";
  bool _isLoading = true;
  bool _isNotLinked = false;
  bool _isNetworkError = false;
  String _networkErrorMessage =
      "Unable to connect to server.\nPlease check your network connection and retry.";
  final String _unlinkedMessage =
      "Student profile is not linked to this account.\nPlease contact the administrator.";

  @override
  void initState() {
    super.initState();
    _initStudentData();
  }

  void _applyStudentData(Map<String, dynamic> s) {
    setState(() {
      _studentToken = s['qr_token'] ?? s['student_id'] ?? '';
      _studentName = s['full_name'] ?? 'Student';
      _studentId = s['student_id'] ?? '';
      _rollNumber = s['roll_number'] ?? '-';
      _department = s['department_code'] ?? s['department_name'] ?? '-';
      _course = s['course'] ?? '-';
      _semester = s['semester'] != null ? "${s['semester']} Semester" : '-';
      _isNotLinked = false;
      _isNetworkError = false;
    });
  }

  Future<void> _initStudentData() async {
    final user = ApiService().currentUser;
    final isStudent = user != null && user['role'] == 'student';

    if (isStudent) {
      // Automatic identity from authenticated student session
      if (user['student'] is Map<String, dynamic> &&
          (user['student'] as Map<String, dynamic>)['student_id'] != null) {
        _applyStudentData(Map<String, dynamic>.from(user['student']));
        setState(() {
          _isLoading = false;
          _isNotLinked = false;
          _isNetworkError = false;
        });
      } else {
        setState(() {
          _isLoading = true;
        });
      }

      final freshStudent = await ApiService().getCurrentStudent();
      if (!mounted) return;

      if (freshStudent != null) {
        if (freshStudent['error'] == 'NETWORK_ERROR') {
          if (_studentId.isEmpty) {
            setState(() {
              _isLoading = false;
              _isNetworkError = true;
              _isNotLinked = false;
              _networkErrorMessage = freshStudent['message'] ?? _networkErrorMessage;
            });
          } else {
            setState(() {
              _isLoading = false;
            });
          }
          return;
        }

        if (freshStudent['error'] == 'PROFILE_NOT_LINKED') {
          if (_studentId.isEmpty) {
            setState(() {
              _isLoading = false;
              _isNotLinked = true;
              _isNetworkError = false;
            });
          } else {
            setState(() {
              _isLoading = false;
            });
          }
          return;
        }

        if (freshStudent['student_id'] != null) {
          _applyStudentData(freshStudent);
          setState(() {
            _isLoading = false;
            _isNotLinked = false;
            _isNetworkError = false;
          });
          return;
        }
      }

      if (_studentId.isEmpty) {
        setState(() {
          _isLoading = false;
          _isNotLinked = true;
          _isNetworkError = false;
        });
      } else {
        setState(() {
          _isLoading = false;
        });
      }
      return;
    }

    // For Admin / Teacher roles viewing cards
    setState(() {
      _isLoading = true;
    });

    final students = await ApiService().searchStudents("");
    if (students.isNotEmpty && mounted) {
      final s = Map<String, dynamic>.from(students.first);
      _applyStudentData(s);
    }

    if (mounted) {
      setState(() {
        _isLoading = false;
        _isNotLinked = students.isEmpty;
        _isNetworkError = false;
      });
    }
  }

  void _showStudentPicker() async {
    final user = ApiService().currentUser;
    if (user != null && user['role'] == 'student') {
      // Security: Students are never allowed to open student picker
      return;
    }

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
                  final s = Map<String, dynamic>.from(students[i]);
                  return ListTile(
                    leading: CircleAvatar(
                      child: Text((s['full_name'] ?? 'S')[0]),
                    ),
                    title: Text(s['full_name'] ?? 'Student'),
                    subtitle: Text("${s['student_id']} • ${s['roll_number']}"),
                    onTap: () {
                      _applyStudentData(s);
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

  Widget _buildNetworkErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.wifi_off_rounded,
                size: 64,
                color: Colors.redAccent,
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              "Unable to Connect",
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              _networkErrorMessage,
              style: const TextStyle(fontSize: 14, color: Colors.grey, height: 1.5),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 28),
            ElevatedButton.icon(
              onPressed: () {
                setState(() {
                  _isLoading = true;
                  _isNetworkError = false;
                  _isNotLinked = false;
                });
                _initStudentData();
              },
              icon: const Icon(Icons.refresh_rounded),
              label: const Text("Retry Connection"),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUnlinkedView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.amber.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.person_off_rounded,
                size: 64,
                color: Colors.amber,
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              "Student Profile Not Linked",
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              _unlinkedMessage,
              style: const TextStyle(fontSize: 14, color: Colors.grey, height: 1.5),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 28),
            OutlinedButton.icon(
              onPressed: () {
                setState(() {
                  _isLoading = true;
                  _isNotLinked = false;
                  _isNetworkError = false;
                });
                _initStudentData();
              },
              icon: const Icon(Icons.refresh_rounded),
              label: const Text("Check Again"),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final user = ApiService().currentUser;
    final isStudent = user != null && user['role'] == 'student';

    return Scaffold(
      appBar: AppBar(
        title: Text(isStudent ? "My Pass" : "Digital Student ID & QR"),
        actions: isStudent
            ? null
            : [
                IconButton(
                  icon: const Icon(Icons.people_outline),
                  tooltip: "Switch Student Card",
                  onPressed: _showStudentPicker,
                ),
              ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _isNetworkError
              ? _buildNetworkErrorView()
              : _isNotLinked
                  ? _buildUnlinkedView()
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
                                    "DR. VIRENDRA SWARUP MEMORIAL TRUST",
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 10.5,
                                      letterSpacing: 0.2,
                                    ),
                                  ),
                                  Text(
                                    "GROUP OF INSTITUTIONS (VSGOI)",
                                    style: TextStyle(
                                      color: Color(0xFFFDE047),
                                      fontWeight: FontWeight.bold,
                                      fontSize: 10,
                                      letterSpacing: 0.2,
                                    ),
                                  ),
                                  Text(
                                    "Charlestown Institutional Area, Unnao, UP",
                                    style: TextStyle(
                                      color: Colors.white70,
                                      fontSize: 8.5,
                                    ),
                                  ),
                                  SizedBox(height: 2),
                                  Text(
                                    "OFFICIAL STUDENT IDENTITY PASS",
                                    style: TextStyle(
                                      color: Colors.white60,
                                      fontSize: 8.5,
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
                                  data: _studentToken.isNotEmpty ? _studentToken : _studentId,
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

                  if (!isStudent) ...[
                    const SizedBox(height: 20),
                    ElevatedButton.icon(
                      onPressed: _showStudentPicker,
                      icon: const Icon(Icons.swap_horiz),
                      label: const Text("Switch / Select Another Student"),
                    ),
                  ],
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
