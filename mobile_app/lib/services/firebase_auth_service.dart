import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:mobile_app/services/api_service.dart';

class FirebaseAuthService {
  static final FirebaseAuthService _instance = FirebaseAuthService._internal();
  factory FirebaseAuthService() => _instance;
  FirebaseAuthService._internal();

  final FirebaseAuth _auth = FirebaseAuth.instance;
  final GoogleSignIn _googleSignIn = GoogleSignIn();

  User? get currentUser => _auth.currentUser;

  // 1. Email & Password Sign In
  Future<Map<String, dynamic>> signInWithEmailPassword({
    required String email,
    required String password,
  }) async {
    try {
      final userCred = await _auth.signInWithEmailAndPassword(
        email: email.trim(),
        password: password,
      );

      final user = userCred.user;
      if (user == null) {
        return {'success': false, 'message': 'Failed to retrieve user profile.'};
      }

      final idToken = await user.getIdToken();
      if (idToken == null) {
        return {'success': false, 'message': 'Failed to retrieve auth token.'};
      }

      return await ApiService().syncFirebaseLogin(
        idToken: idToken,
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
      );
    } on FirebaseAuthException catch (e) {
      return {'success': false, 'message': e.message ?? 'Authentication error.'};
    } catch (e) {
      return {'success': false, 'message': 'Sign-in error: $e'};
    }
  }

  // 2. Google Sign-In
  Future<Map<String, dynamic>> signInWithGoogle() async {
    try {
      final googleUser = await _googleSignIn.signIn();
      if (googleUser == null) {
        return {'success': false, 'message': 'Google sign-in was cancelled.'};
      }

      final googleAuth = await googleUser.authentication;
      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );

      final userCred = await _auth.signInWithCredential(credential);
      final user = userCred.user;
      if (user == null) {
        return {'success': false, 'message': 'Failed to retrieve user from Google.'};
      }

      final idToken = await user.getIdToken();
      if (idToken == null) {
        return {'success': false, 'message': 'Failed to retrieve auth token from Google.'};
      }

      return await ApiService().syncFirebaseLogin(
        idToken: idToken,
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
      );
    } on FirebaseAuthException catch (e) {
      return {'success': false, 'message': e.message ?? 'Google authentication error.'};
    } catch (e) {
      return {'success': false, 'message': 'Google sign-in error: $e'};
    }
  }

  // 3. Phone Number Verification (SMS OTP)
  Future<void> sendPhoneOtp({
    required String phoneNumber,
    required Function(String verificationId, int? resendToken) onCodeSent,
    required Function(FirebaseAuthException error) onVerificationFailed,
    required Function(PhoneAuthCredential credential) onAutoVerify,
  }) async {
    await _auth.verifyPhoneNumber(
      phoneNumber: phoneNumber.trim(),
      verificationCompleted: onAutoVerify,
      verificationFailed: onVerificationFailed,
      codeSent: onCodeSent,
      codeAutoRetrievalTimeout: (String verificationId) {},
      timeout: const Duration(seconds: 60),
    );
  }

  Future<Map<String, dynamic>> verifyPhoneOtp({
    required String verificationId,
    required String smsCode,
  }) async {
    try {
      final credential = PhoneAuthProvider.credential(
        verificationId: verificationId,
        smsCode: smsCode.trim(),
      );

      final userCred = await _auth.signInWithCredential(credential);
      final user = userCred.user;
      if (user == null) {
        return {'success': false, 'message': 'Phone verification failed.'};
      }

      final idToken = await user.getIdToken();
      if (idToken == null) {
        return {'success': false, 'message': 'Failed to retrieve auth token.'};
      }

      return await ApiService().syncFirebaseLogin(
        idToken: idToken,
        uid: user.uid,
        phoneNumber: user.phoneNumber,
        displayName: user.displayName,
      );
    } on FirebaseAuthException catch (e) {
      return {'success': false, 'message': e.message ?? 'Invalid verification code.'};
    } catch (e) {
      return {'success': false, 'message': 'Verification error: $e'};
    }
  }

  // 4. Sign Out
  Future<void> signOut() async {
    try {
      await _googleSignIn.signOut();
    } catch (_) {}
    await _auth.signOut();
    await ApiService().logout();
  }
}
