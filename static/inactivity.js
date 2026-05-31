// --- Global Inactivity Timer ---
let inactivityTimer;
const INACTIVITY_TIME = 60000; // 1 minute

function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    inactivityTimer = setTimeout(() => {
        // Redirect to welcome screen if inactive for 1 minute
        window.location.href = '/';
    }, INACTIVITY_TIME);
}

// Reset timer on any user interaction
['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'].forEach(evt => {
    document.addEventListener(evt, resetInactivityTimer, true);
});

// Initialize on page load
resetInactivityTimer();
