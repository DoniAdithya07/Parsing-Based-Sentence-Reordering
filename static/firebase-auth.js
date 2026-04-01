import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/10.13.2/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  signOut,
  onAuthStateChanged,
  setPersistence,
  browserLocalPersistence,
} from "https://www.gstatic.com/firebasejs/10.13.2/firebase-auth.js";
import { getAnalytics, isSupported } from "https://www.gstatic.com/firebasejs/10.13.2/firebase-analytics.js";

let auth = null;
let isSigningIn = false;

const DEFAULT_FIREBASE_CONFIG = {
  apiKey: "AIzaSyAm-MM0bHIpMf2cv0AlCYrRLM8CjRPYVr4",
  authDomain: "parsing-based-sentence.firebaseapp.com",
  projectId: "parsing-based-sentence",
  storageBucket: "parsing-based-sentence.firebasestorage.app",
  messagingSenderId: "1024287457881",
  appId: "1:1024287457881:web:6ccf038e021c7cd6bc6748",
  measurementId: "G-E73J28BK20",
};

const REQUIRED_AUTH_CONFIG_FIELDS = ["apiKey", "authDomain", "projectId", "appId"];
const OPTIONAL_CONFIG_FIELDS = ["storageBucket", "messagingSenderId"];

function isValidAuthConfig(cfg) {
  if (!cfg) return false;
  const missingRequired = REQUIRED_AUTH_CONFIG_FIELDS.filter((field) => !cfg[field]);
  return missingRequired.length === 0;
}

function readFirebaseConfig() {
  const node = document.getElementById("firebase-config");

  if (node) {
    try {
      const cfg = JSON.parse(node.textContent || "{}");
      if (isValidAuthConfig(cfg)) {
        const missingOptional = OPTIONAL_CONFIG_FIELDS.filter((field) => !cfg[field]);
        if (missingOptional.length) {
          console.warn("Firebase optional config missing:", missingOptional.join(", "));
        }
        return cfg;
      }
      console.warn("Template Firebase config invalid. Using fallback config.");
    } catch (error) {
      console.error("Failed to parse template Firebase config:", error);
    }
  }

  if (isValidAuthConfig(DEFAULT_FIREBASE_CONFIG)) {
    return DEFAULT_FIREBASE_CONFIG;
  }

  console.error("No valid Firebase config available.");
  return null;
}

function ensureToastContainer() {
  let container = document.getElementById("toast-container");
  if (container) return container;

  container = document.createElement("div");
  container.id = "toast-container";
  container.className = "toast-container";
  document.body.appendChild(container);
  return container;
}

function showToast(message, type = "success") {
  const container = ensureToastContainer();
  const toast = document.createElement("div");
  toast.className = `toast toast-${type === "error" ? "error" : "success"}`;
  toast.textContent = message;
  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 220);
  }, 3200);
}

function getInitials(nameOrEmail) {
  const value = (nameOrEmail || "U").trim();
  if (!value) return "U";

  const words = value.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return value.slice(0, 2).toUpperCase();
}

function setLoginButtonState({ busy, text }) {
  const loginBtn = document.getElementById("login-btn");
  if (!loginBtn) return;

  if (!loginBtn.dataset.defaultText) {
    loginBtn.dataset.defaultText = loginBtn.textContent || "Login with Google";
  }

  loginBtn.disabled = Boolean(busy);
  loginBtn.textContent = text || loginBtn.dataset.defaultText;
  loginBtn.classList.toggle("auth-disabled", Boolean(busy));
}

function ensureSessionMessage() {
  const authSection = document.querySelector(".auth-section");
  if (!authSection) return null;

  let note = document.getElementById("session-note");
  if (note) return note;

  note = document.createElement("small");
  note.id = "session-note";
  note.className = "session-note";
  note.textContent = "Session saved automatically";
  note.style.display = "none";
  authSection.appendChild(note);
  return note;
}

function setGuestMode(isGuest) {
  const form = document.getElementById("reorder-form");
  if (!form) return;

  const submitButtons = form.querySelectorAll('button[type="submit"]');
  submitButtons.forEach((button) => {
    button.disabled = false;
    button.classList.toggle("guest-mode-btn", isGuest);
  });

  const message = document.getElementById("auth-required-msg");
  if (message) {
    message.textContent = isGuest ? "Login to unlock full features" : "";
    message.style.display = isGuest ? "block" : "none";
  }
}

function updateAuthUI(user) {
  const userInfo = document.getElementById("user-info");
  const loginBtn = document.getElementById("login-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const avatar = document.getElementById("user-avatar");
  const sessionNote = ensureSessionMessage();

  if (!userInfo || !loginBtn || !logoutBtn || !avatar) return;

  if (user) {
    const displayName = user.displayName || user.email || "Google User";
    userInfo.textContent = displayName;
    loginBtn.style.display = "none";
    logoutBtn.style.display = "inline-flex";

    avatar.title = `Logged in as: ${displayName}`;
    if (user.photoURL) {
      avatar.textContent = "";
      avatar.style.backgroundImage = `url('${user.photoURL}')`;
      avatar.classList.add("has-photo");
    } else {
      avatar.textContent = getInitials(displayName);
      avatar.style.backgroundImage = "none";
      avatar.classList.remove("has-photo");
    }

    if (sessionNote) sessionNote.style.display = "inline-block";
    setGuestMode(false);
    setLoginButtonState({ busy: false });
  } else {
    userInfo.textContent = "";
    loginBtn.style.display = "inline-flex";
    logoutBtn.style.display = "none";
    avatar.textContent = "U";
    avatar.style.backgroundImage = "none";
    avatar.classList.remove("has-photo");
    avatar.title = "Guest user";

    if (sessionNote) sessionNote.style.display = "none";
    setGuestMode(true);
    setLoginButtonState({ busy: false });
  }
}

function mapAuthErrorToMessage(error) {
  if (!error) return "Login failed";

  if (error.code === "auth/popup-blocked") return "Popup was blocked. Switched to redirect login.";
  if (error.code === "auth/popup-closed-by-user") return "Login popup was closed.";
  if (error.code === "auth/network-request-failed") return "Network error. Check internet and try again.";
  if (error.code === "auth/unauthorized-domain") return "This domain is not authorized in Firebase Auth settings.";
  if (error.code === "auth/operation-not-allowed") return "Google sign-in is not enabled in Firebase console.";
  if (error.code === "auth/invalid-api-key") return "Firebase API key is invalid.";

  return error.message || "Login failed. Please try again.";
}

function shouldFallbackToRedirect(error) {
  return error && ["auth/popup-blocked", "auth/popup-closed-by-user", "auth/cancelled-popup-request"].includes(error.code);
}

async function signInWithGoogle() {
  if (!auth) {
    showToast("Firebase config missing", "error");
    return;
  }
  if (isSigningIn) return;

  isSigningIn = true;
  setLoginButtonState({ busy: true, text: "Signing in..." });

  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });

  try {
    await signInWithPopup(auth, provider);
    showToast("Logged in successfully", "success");
  } catch (error) {
    console.error("Google sign-in failed:", error.code, error.message);

    if (shouldFallbackToRedirect(error)) {
      showToast("Popup blocked. Redirecting to Google sign-in...", "error");
      await signInWithRedirect(auth, provider);
      return;
    }

    showToast(mapAuthErrorToMessage(error), "error");
    setLoginButtonState({ busy: false });
  } finally {
    isSigningIn = false;
  }
}

async function logout() {
  if (!auth) return;

  const confirmed = window.confirm("Are you sure you want to logout?");
  if (!confirmed) return;

  try {
    await signOut(auth);
    showToast("Logged out", "success");
  } catch (error) {
    console.error("Logout failed:", error);
    showToast("Logout failed", "error");
  }
}

async function initAnalytics(app) {
  try {
    const supported = await isSupported();
    if (supported) {
      getAnalytics(app);
      console.info("Firebase analytics initialized.");
    }
  } catch (error) {
    console.warn("Firebase analytics not initialized:", error);
  }
}

async function initFirebaseAuth() {
  const cfg = readFirebaseConfig();

  if (!cfg) {
    const loginBtn = document.getElementById("login-btn");
    if (loginBtn) {
      loginBtn.disabled = true;
      loginBtn.title = "Firebase config missing";
    }
    setGuestMode(true);
    showToast("Firebase config missing. Running in guest mode.", "error");
    return;
  }

  const app = getApps().length ? getApps()[0] : initializeApp(cfg);
  auth = getAuth(app);

  try {
    await setPersistence(auth, browserLocalPersistence);
  } catch (error) {
    console.warn("Could not set auth persistence:", error);
  }

  initAnalytics(app);

  try {
    const redirectResult = await getRedirectResult(auth);
    if (redirectResult && redirectResult.user) {
      showToast("Logged in successfully", "success");
    }
  } catch (error) {
    console.error("Redirect login result error:", error.code, error.message);
    showToast(mapAuthErrorToMessage(error), "error");
  }

  onAuthStateChanged(auth, (user) => {
    updateAuthUI(user);
  });
}

window.signInWithGoogle = signInWithGoogle;
window.logout = logout;
window.showToast = showToast;

document.addEventListener("DOMContentLoaded", () => {
  initFirebaseAuth();
});