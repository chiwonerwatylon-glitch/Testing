/**
 * First Mutual Life Requisition System
 * Main JavaScript File
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(el => new bootstrap.Tooltip(el));

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });

    // Fetch dashboard stats for badge counts
    fetchStats();

    // Confirm dangerous actions
    document.querySelectorAll('[data-confirm]').forEach(el => {
        el.addEventListener('click', function(e) {
            if (!confirm(this.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });
});

function fetchStats() {
    const pendingReviewBadge = document.getElementById('pending-review-count');
    const pendingApprovalBadge = document.getElementById('pending-approval-count');

    if (pendingReviewBadge || pendingApprovalBadge) {
        fetch('/api/requisitions/stats')
            .then(response => response.json())
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
            .catch(err => console.log('Stats fetch error:', err));
    }
}

/**
 * Format currency display
 */
function formatCurrency(amount, currency = 'USD') {
    const symbols = {
        'USD': '$',
        'ZWG': 'ZWG$',
        'ZAR': 'R',
        'BWP': 'P'
    };
    const symbol = symbols[currency] || currency;
    return `${symbol}${parseFloat(amount).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
}

/**
 * Show loading spinner
 */
function showLoading() {
    const overlay = document.createElement('div');
    overlay.className = 'spinner-overlay';
    overlay.id = 'loadingSpinner';
    overlay.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2 text-muted">Processing...</p>
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
 * Show loading on form submit for downloads
 */
document.addEventListener('click', function(e) {
    if (e.target.closest('a[href*="/download/"]')) {
        showLoading();
        setTimeout(hideLoading, 3000);
    }
});

/**
 * Validate file size before upload
 */
function validateFileSize(input, maxSizeMB = 5) {
    if (input.files && input.files[0]) {
        const fileSize = input.files[0].size / 1024 / 1024; // MB
        if (fileSize > maxSizeMB) {
            alert(`File size exceeds ${maxSizeMB}MB limit. Please choose a smaller file.`);
            input.value = '';
            return false;
        }
    }
    return true;
}

// Apply file size validation to all signature inputs
document.querySelectorAll('input[type="file"][name="signature"]').forEach(input => {
    input.addEventListener('change', function() {
        validateFileSize(this, 5);
    });
});
