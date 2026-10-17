/**
 * First Mutual Life Requisition System
 * Main JavaScript File
 *
 * Bootstrap 5-based behaviours:
 * - Tooltips, Alerts
 * - Data-driven confirmations
 * - Theme toggle using data-bs-theme (light/dark)
 * - Stats badges fetch
 * - Loading overlay
 * - File-size validation
 */

document.addEventListener('DOMContentLoaded', function () {
    /* -----------------------------------------
     * BOOTSTRAP COMPONENT INITIALISATION
     * -------------------------------------- */

    // Tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].forEach(el => {
        new bootstrap.Tooltip(el);
    });

    // Auto-dismiss alerts after 5 seconds (unless .alert-permanent)
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });

    /* -----------------------------------------
     * THEME HANDLING (LIGHT / DARK)
     * -------------------------------------- */

    // Determine initial theme: localStorage > OS preference > default 'light'
    const storedTheme = localStorage.getItem('fml-theme');
    const prefersDark = window.matchMedia &&
        window.matchMedia('(prefers-color-scheme: dark)').matches;

    const initialTheme = storedTheme || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-bs-theme', initialTheme);

    const themeToggle = document.getElementById('themeToggle');

    function applyThemeIcon() {
        if (!themeToggle) return;
        const icon = themeToggle.querySelector('i');
        if (!icon) return;

        const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        // Using Bootstrap Icons classes as per Bootstrap model
        icon.classList.toggle('bi-moon-stars', !isDark);
        icon.classList.toggle('bi-sun', isDark);
    }

    if (themeToggle) {
        applyThemeIcon();
        themeToggle.addEventListener('click', function () {
            const current = document.documentElement.getAttribute('data-bs-theme') || 'light';
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-bs-theme', next);
            localStorage.setItem('fml-theme', next);
            applyThemeIcon();
        });
    }

    /* -----------------------------------------
     * CONFIRM DANGEROUS ACTIONS (data-confirm)
     * -------------------------------------- */
    document.querySelectorAll('[data-confirm]').forEach(el => {
        el.addEventListener('click', function (e) {
            const message = this.getAttribute('data-confirm') || 'Are you sure?';
            if (!window.confirm(message)) {
                e.preventDefault();
            }
        });
    });

    /* -----------------------------------------
     * DASHBOARD STATS (BADGE COUNTS)
     * -------------------------------------- */
    fetchStats();

    /* -----------------------------------------
     * FILE SIZE VALIDATION FOR SIGNATURES
     * -------------------------------------- */
    document.querySelectorAll('input[type="file"][name="signature"]').forEach(input => {
        input.addEventListener('change', function () {
            validateFileSize(this, 5);
        });
    });
});

/* =========================================
 * DASHBOARD STATS
 * ======================================= */
function fetchStats() {
    const pendingReviewBadge = document.getElementById('pending-review-count');
    const pendingApprovalBadge = document.getElementById('pending-approval-count');

    if (!pendingReviewBadge && !pendingApprovalBadge) return;

    fetch('/api/requisitions/stats', {
        headers: {
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok for stats');
            }
            return response.json();
        })
        .then(data => {
            if (pendingReviewBadge) {
                if (data.pending_review > 0) {
                    pendingReviewBadge.textContent = data.pending_review;
                    pendingReviewBadge.style.display = 'inline-block';
                } else {
                    pendingReviewBadge.style.display = 'none';
                }
            }

            if (pendingApprovalBadge) {
                if (data.pending_approval > 0) {
                    pendingApprovalBadge.textContent = data.pending_approval;
                    pendingApprovalBadge.style.display = 'inline-block';
                } else {
                    pendingApprovalBadge.style.display = 'none';
                }
            }
        })
        .catch(err => {
            // Keep silent in UI, just log
            console.log('Stats fetch error:', err);
        });
}

/* =========================================
 * CURRENCY FORMATTING (UI HELPER)
 * ======================================= */
function formatCurrency(amount, currency = 'USD') {
    const symbols = {
        'USD': '$',
        'ZWG': 'ZWG$',
        'ZWL': 'ZWL$',   // optional: add more mappings if needed
        'ZAR': 'R',
        'BWP': 'P'
    };

    const symbol = symbols[currency] || `${currency} `;
    const numericAmount = Number.parseFloat(amount || 0);

    if (Number.isNaN(numericAmount)) {
        return `${symbol}0.00`;
    }

    return `${symbol}${numericAmount.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })}`;
}

/* =========================================
 * LOADING SPINNER OVERLAY (Bootstrap-style)
 * ======================================= */
function showLoading(message = 'Processing...') {
    if (document.getElementById('loadingSpinner')) return;

    const overlay = document.createElement('div');
    overlay.className = 'spinner-overlay d-flex align-items-center justify-content-center';
    overlay.id = 'loadingSpinner';
    overlay.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2 text-muted">${message}</p>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hideLoading() {
    const overlay = document.getElementById('loadingSpinner');
    if (overlay) {
        overlay.remove();
    }
}

/**
 * Show loading on click for download links (simple UX helper)
 */
document.addEventListener('click', function (e) {
    const link = e.target.closest('a[href*="/download/"]');
    if (!link) return;

    showLoading('Preparing your download...');
    // Fallback: hide loading after 3 seconds in case the browser
    // download dialog appears and we have no other signal
    setTimeout(hideLoading, 3000);
});

/* =========================================
 * FILE SIZE VALIDATION
 * ======================================= */
function validateFileSize(input, maxSizeMB = 5) {
    if (input.files && input.files[0]) {
        const fileSizeMB = input.files[0].size / 1024 / 1024;
        if (fileSizeMB > maxSizeMB) {
            alert(`File size exceeds ${maxSizeMB}MB limit. Please choose a smaller file.`);
            input.value = '';
            return false;
        }
    }
    return true;
}

/* =========================================
 * EXPORTS (if using modules/bundler)
 * ======================================= */
// If you later use ES modules / bundlers, you can export helpers:
// export { fetchStats, formatCurrency, showLoading, hideLoading, validateFileSize };
