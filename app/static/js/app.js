/**
 * QR ATTENDANCE ERP SYSTEM V2.0 - Core Application JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initSidebar();
  initTooltips();
  setupAudioFeedback();
});

/* -------------------------------------------------------------------------- */
/* Theme Management (Light / Dark)                                            */
/* -------------------------------------------------------------------------- */
function initTheme() {
  const toggleBtn = document.getElementById('theme-toggle-btn');
  const themeIcon = document.getElementById('theme-toggle-icon');

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    localStorage.setItem('theme', theme);
    if (themeIcon) {
      if (theme === 'dark') {
        themeIcon.classList.remove('bi-moon-stars-fill');
        themeIcon.classList.add('bi-sun-fill');
      } else {
        themeIcon.classList.remove('bi-sun-fill');
        themeIcon.classList.add('bi-moon-stars-fill');
      }
    }
  }

  // Determine current theme
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialTheme = savedTheme || (prefersDark ? 'dark' : 'light');
  applyTheme(initialTheme);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-bs-theme') || 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
    });
  }

  // React to OS changes if user hasn't explicitly set preference
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });
}

/* -------------------------------------------------------------------------- */
/* Sidebar & Mobile Navigation                                                */
/* -------------------------------------------------------------------------- */
function initSidebar() {
  const sidebar = document.getElementById('appSidebar');
  const toggleBtn = document.getElementById('sidebarToggleBtn');
  const backdrop = document.getElementById('sidebarBackdrop');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('show');
      if (backdrop) backdrop.classList.toggle('show');
    });
  }

  if (backdrop && sidebar) {
    backdrop.addEventListener('click', () => {
      sidebar.classList.remove('show');
      backdrop.classList.remove('show');
    });
  }
}

/* -------------------------------------------------------------------------- */
/* Tooltips                                                                   */
/* -------------------------------------------------------------------------- */
function initTooltips() {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.forEach((el) => {
    new bootstrap.Tooltip(el);
  });
}

/* -------------------------------------------------------------------------- */
/* Toast Notification Helper                                                  */
/* -------------------------------------------------------------------------- */
window.showToast = function(message, type = 'info', title = 'Notification') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const bgClasses = {
    success: 'bg-success text-white',
    danger: 'bg-danger text-white',
    warning: 'bg-warning text-dark',
    info: 'bg-info text-white'
  };

  const icons = {
    success: 'bi-check-circle-fill',
    danger: 'bi-exclamation-octagon-fill',
    warning: 'bi-exclamation-triangle-fill',
    info: 'bi-info-circle-fill'
  };

  const toastId = 'toast-' + Date.now();
  const html = `
    <div id="${toastId}" class="toast align-items-center ${bgClasses[type] || bgClasses.info} border-0 mb-2 shadow" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <i class="bi ${icons[type] || icons.info} fs-5"></i>
          <div>
            <strong>${title}:</strong> ${message}
          </div>
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;

  container.insertAdjacentHTML('beforeend', html);
  const toastEl = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastEl, { delay: 4500 });
  toast.show();

  toastEl.addEventListener('hidden.bs.toast', () => {
    toastEl.remove();
  });
};

/* -------------------------------------------------------------------------- */
/* Web Audio API Sound Feedback (No external asset files required!)            */
/* -------------------------------------------------------------------------- */
let audioCtx = null;

function setupAudioFeedback() {
  // Lazily initialize audio context on first user interaction
  const initAudio = () => {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
  };
  document.addEventListener('click', initAudio, { once: true });
}

window.playSuccessChime = function() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') audioCtx.resume();

    const now = audioCtx.currentTime;
    const osc1 = audioCtx.createOscillator();
    const osc2 = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(587.33, now); // D5
    osc1.frequency.setValueAtTime(880.00, now + 0.08); // A5

    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(880.00, now + 0.08);

    gain.gain.setValueAtTime(0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(audioCtx.destination);

    osc1.start(now);
    osc2.start(now + 0.08);
    osc1.stop(now + 0.35);
    osc2.stop(now + 0.35);
  } catch (e) {
    console.debug('Audio error:', e);
  }
};

window.playWarningBeep = function() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') audioCtx.resume();

    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(320, now);
    osc.frequency.setValueAtTime(240, now + 0.1);

    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);

    osc.connect(gain);
    gain.connect(audioCtx.destination);

    osc.start(now);
    osc.stop(now + 0.3);
  } catch (e) {
    console.debug('Audio error:', e);
  }
};
