import 'package:flutter/material.dart';
import 'package:mobile_app/services/api_service.dart';

class ResetDataScreen extends StatefulWidget {
  const ResetDataScreen({super.key});

  @override
  State<ResetDataScreen> createState() => _ResetDataScreenState();
}

class _ResetDataScreenState extends State<ResetDataScreen> {
  String _selectedMode = 'ATTENDANCE';
  bool _isLoadingPreview = false;
  Map<String, dynamic>? _previewData;

  @override
  void initState() {
    super.initState();
    _fetchPreview('ATTENDANCE');
  }

  Future<void> _fetchPreview(String mode) async {
    setState(() {
      _selectedMode = mode;
      _isLoadingPreview = true;
    });

    final res = await ApiService().getResetPreview(mode);
    if (!mounted) return;

    setState(() {
      _isLoadingPreview = false;
      if (res['success'] == true && res['preview'] != null) {
        _previewData = Map<String, dynamic>.from(res['preview']);
      } else {
        _previewData = null;
      }
    });
  }

  void _showExecutionDialog() {
    final confirmCtrl = TextEditingController();
    final passwordCtrl = TextEditingController();
    final requiresPassword = _selectedMode != 'ATTENDANCE';
    bool isSubmitting = false;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          final isConfirmValid = confirmCtrl.text.trim() == 'RESET DATA';
          final isPasswordValid = !requiresPassword || passwordCtrl.text.trim().isNotEmpty;
          final canSubmit = isConfirmValid && isPasswordValid && !isSubmitting;

          return AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
            title: Row(
              children: [
                const Icon(Icons.warning_rounded, color: Colors.redAccent, size: 26),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    "Confirm $_selectedMode Reset",
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      _previewData?['scope_description'] ??
                          "This destructive action cannot be undone. All affected rows will be permanently deleted.",
                      style: const TextStyle(fontSize: 12, color: Colors.redAccent, fontWeight: FontWeight.w600),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    "Type 'RESET DATA' to confirm:",
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: confirmCtrl,
                    decoration: InputDecoration(
                      hintText: "RESET DATA",
                      hintStyle: TextStyle(color: Colors.grey.withValues(alpha: 0.6)),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    ),
                    onChanged: (_) => setModalState(() {}),
                  ),
                  if (requiresPassword) ...[
                    const SizedBox(height: 14),
                    const Text(
                      "Admin Password:",
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 6),
                    TextField(
                      controller: passwordCtrl,
                      obscureText: true,
                      decoration: InputDecoration(
                        hintText: "Enter your admin password",
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      ),
                      onChanged: (_) => setModalState(() {}),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: isSubmitting ? null : () => Navigator.pop(ctx),
                child: const Text("Cancel"),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.redAccent,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: canSubmit
                    ? () async {
                        final messenger = ScaffoldMessenger.of(context);
                        final navigator = Navigator.of(ctx);

                        setModalState(() => isSubmitting = true);
                        final res = await ApiService().executeResetData(
                          type: _selectedMode,
                          confirmText: confirmCtrl.text.trim(),
                          password: passwordCtrl.text.trim(),
                        );
                        if (!mounted) return;
                        navigator.pop();

                        if (res['success'] == true) {
                          messenger.showSnackBar(
                            SnackBar(
                              backgroundColor: Colors.green.shade700,
                              content: Text(res['message'] ?? "Reset executed successfully."),
                            ),
                          );
                          _fetchPreview(_selectedMode);
                        } else {
                          messenger.showSnackBar(
                            SnackBar(
                              backgroundColor: Colors.redAccent,
                              content: Text(res['message'] ?? "Failed to execute reset."),
                            ),
                          );
                        }
                      }
                    : null,
                child: isSubmitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                      )
                    : const Text("Execute Reset"),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildModeCard({
    required String mode,
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
  }) {
    final isSelected = _selectedMode == mode;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return InkWell(
      onTap: () => _fetchPreview(mode),
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isSelected
              ? color.withValues(alpha: isDark ? 0.2 : 0.1)
              : (isDark ? const Color(0xFF1E293B) : Colors.white),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? color : Colors.grey.withValues(alpha: 0.25),
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: isSelected ? color : null,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 12,
                      color: isDark ? Colors.white70 : Colors.black54,
                    ),
                  ),
                ],
              ),
            ),
            if (isSelected)
              Icon(Icons.check_circle_rounded, color: color, size: 20),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Reset Data & Start Fresh"),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Warning Banner
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
              ),
              child: const Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.shield_rounded, color: Colors.redAccent, size: 28),
                  SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          "DESTRUCTIVE DATA OPERATIONS",
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: Colors.redAccent,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          "Resetting data removes operational rows from the database. A pre-reset snapshot is recorded before deletion. Master admin access is preserved.",
                          style: TextStyle(fontSize: 12, color: Colors.redAccent),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            const Text(
              "SELECT RESET MODE",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 0.5),
            ),
            const SizedBox(height: 10),

            _buildModeCard(
              mode: 'ATTENDANCE',
              title: "Reset Attendance Data",
              subtitle: "Clears attendance records & punch logs. Retains students & faculty.",
              icon: Icons.calendar_today_rounded,
              color: Colors.amber.shade800,
            ),
            const SizedBox(height: 10),

            _buildModeCard(
              mode: 'OPERATIONAL',
              title: "Reset Operational ERP Data",
              subtitle: "Clears students, faculty & assignments for fresh intake.",
              icon: Icons.people_alt_rounded,
              color: Colors.deepOrange,
            ),
            const SizedBox(height: 10),

            _buildModeCard(
              mode: 'FACTORY',
              title: "Full Factory Reset",
              subtitle: "Pristine initial installation state. Preserves Super Admin.",
              icon: Icons.local_fire_department_rounded,
              color: Colors.redAccent,
            ),

            const SizedBox(height: 24),

            // Preview Section
            const Text(
              "AFFECTED DATABASE RECORDS",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 0.5),
            ),
            const SizedBox(height: 10),

            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Theme.of(context).brightness == Brightness.dark
                    ? const Color(0xFF1E293B)
                    : Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
              ),
              child: _isLoadingPreview
                  ? const Center(child: CircularProgressIndicator())
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _previewData?['scope_description'] ?? "Loading scope...",
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _previewData?['preserved_description'] ?? "",
                          style: TextStyle(
                            fontSize: 12,
                            color: Theme.of(context).brightness == Brightness.dark
                                ? Colors.white60
                                : Colors.black54,
                          ),
                        ),
                        const Divider(height: 24),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceAround,
                          children: [
                            _buildCountItem("Attendance", _previewData?['attendance_count']?.toString() ?? "0"),
                            _buildCountItem("Students", _previewData?['students_count']?.toString() ?? "0"),
                            _buildCountItem("Teachers", _previewData?['teachers_count']?.toString() ?? "0"),
                          ],
                        ),
                      ],
                    ),
            ),

            const SizedBox(height: 28),

            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.redAccent,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                icon: const Icon(Icons.delete_forever_rounded),
                label: Text(
                  "Continue to Reset ($_selectedMode)",
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                onPressed: _isLoadingPreview ? null : _showExecutionDialog,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCountItem(String label, String value) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.redAccent),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: Colors.grey),
        ),
      ],
    );
  }
}
