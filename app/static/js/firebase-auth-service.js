// Firebase Authentication & Client Service for ERP
// Project: erpvsgoi | App ID: 1:574936907832:web:65332fbb59cd2d3dfae6cd

import { initializeApp, getApps, getApp } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import {
  getAuth,
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  signOut,
  onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import {
  getFirestore,
  doc,
  getDoc,
  setDoc,
  collection,
  query,
  getDocs
} from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyB7a8nt-kYYiT97sruPGD6-gCSErpRqTPg",
  authDomain: "erpvsgoi.firebaseapp.com",
  projectId: "erpvsgoi",
  storageBucket: "erpvsgoi.firebasestorage.app",
  messagingSenderId: "574936907832",
  appId: "1:574936907832:web:65332fbb59cd2d3dfae6cd",
  measurementId: "G-T4B0WJ3E7P"
};

const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

class FirebaseAuthService {
  constructor() {
    this.auth = auth;
    this.db = db;
    this.recaptchaVerifier = null;
    this.phoneConfirmationResult = null;
  }

  // 1. Email & Password Sign In
  async signInWithEmail(email, password) {
    const userCredential = await signInWithEmailAndPassword(this.auth, email, password);
    const idToken = await userCredential.user.getIdToken();
    return this.syncWithBackend(idToken, userCredential.user);
  }

  // 2. Google Sign-In
  async signInWithGoogle() {
    try {
      const result = await signInWithPopup(this.auth, googleProvider);
      const idToken = await result.user.getIdToken();
      return this.syncWithBackend(idToken, result.user);
    } catch (err) {
      if (err.code === 'auth/unauthorized-domain' || (err.message && err.message.includes('unauthorized-domain'))) {
        const host = window.location.hostname;
        const enhancedError = new Error(
          `Domain "${host}" is not in Firebase's Authorized Domains list for project 'erpvsgoi'. ` +
          `Please add "${host}" under Firebase Console > Authentication > Settings > Authorized domains.`
        );
        enhancedError.code = 'auth/unauthorized-domain';
        enhancedError.unauthorizedHost = host;
        throw enhancedError;
      }
      throw err;
    }
  }

  // 3. Phone Number Authentication
  initPhoneRecaptcha(containerId = 'recaptcha-container') {
    if (this.recaptchaVerifier) {
      try {
        this.recaptchaVerifier.clear();
      } catch (e) {
        // ignore
      }
      this.recaptchaVerifier = null;
    }

    this.recaptchaVerifier = new RecaptchaVerifier(this.auth, containerId, {
      size: 'invisible',
      callback: () => {
        // reCAPTCHA solved
      },
      'expired-callback': () => {
        if (this.recaptchaVerifier) {
          try { this.recaptchaVerifier.clear(); } catch (e) {}
          this.recaptchaVerifier = null;
        }
      }
    });
    return this.recaptchaVerifier;
  }

  async sendPhoneOtp(phoneNumber, containerId = 'recaptcha-container') {
    try {
      const verifier = this.initPhoneRecaptcha(containerId);
      this.phoneConfirmationResult = await signInWithPhoneNumber(this.auth, phoneNumber, verifier);
      return this.phoneConfirmationResult;
    } catch (err) {
      if (this.recaptchaVerifier) {
        try { this.recaptchaVerifier.clear(); } catch (e) {}
        this.recaptchaVerifier = null;
      }
      if (err.code === 'auth/configuration-not-found' || (err.message && err.message.includes('configuration-not-found'))) {
        const enhancedError = new Error(
          "Phone Authentication is not enabled in Firebase project 'erpvsgoi'. Please enable 'Phone' under Firebase Console > Authentication > Sign-in method."
        );
        enhancedError.code = 'auth/configuration-not-found';
        throw enhancedError;
      }
      throw err;
    }
  }

  async verifyPhoneOtp(otpCode) {
    if (!this.phoneConfirmationResult) {
      throw new Error("No active verification session. Please request OTP first.");
    }
    const result = await this.phoneConfirmationResult.confirm(otpCode);
    const idToken = await result.user.getIdToken();
    return this.syncWithBackend(idToken, result.user);
  }

  // 4. Synchronize Firebase Token with Flask Backend
  async syncWithBackend(idToken, user) {
    const payload = {
      id_token: idToken,
      uid: user.uid,
      email: user.email || '',
      phone_number: user.phoneNumber || '',
      display_name: user.displayName || '',
      photo_url: user.photoURL || ''
    };

    const res = await fetch('/auth/firebase-login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.message || 'Failed to authenticate session with ERP backend.');
    }

    return data;
  }

  // 5. Sign Out
  async signOutUser() {
    await signOut(this.auth);
  }
}

export const firebaseAuthService = new FirebaseAuthService();
window.FirebaseAuthService = firebaseAuthService;
