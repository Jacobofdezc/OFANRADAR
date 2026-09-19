/* ==========================================================================
   BUSINESS RADAR PRIVACY-FRIENDLY ANALYTICS TRACKER (FEATURE 22)
   ========================================================================== */

(function() {
    window.RadarAnalytics = {
        track: function(eventType, properties = {}) {
            try {
                let userObj = null;
                try {
                    userObj = JSON.parse(localStorage.getItem('radar_user') || '{}');
                } catch(e) {}

                const payload = {
                    event_type: eventType,
                    page: window.location.pathname,
                    user_id: userObj.user_id || 'anonymous',
                    properties: properties
                };

                if (navigator.sendBeacon) {
                    navigator.sendBeacon('/v1/analytics/event', JSON.stringify(payload));
                } else {
                    fetch('/v1/analytics/event', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    }).catch(() => {});
                }
            } catch (err) {
                console.warn('[Analytics] Failed to send telemetry:', err);
            }
        }
    };

    // Auto-track page view
    document.addEventListener('DOMContentLoaded', function() {
        RadarAnalytics.track('page_view', { referrer: document.referrer });

        // Auto-attach listeners to conversion CTA buttons
        document.body.addEventListener('click', function(e) {
            const btn = e.target.closest('button, a');
            if (!btn) return;

            if (btn.id === 'btn-export-csv' || btn.classList.contains('fa-file-csv')) {
                RadarAnalytics.track('export_csv_click');
            } else if (btn.id === 'btn-nav-trial' || btn.classList.contains('btn-hero-primary')) {
                RadarAnalytics.track('start_trial_click');
            } else if (btn.id === 'trial-status-badge' || btn.classList.contains('btn-modal-submit')) {
                RadarAnalytics.track('upgrade_modal_click');
            } else if (btn.id === 'btn-watchlist-dropdown') {
                RadarAnalytics.track('add_to_watchlist_click');
            }
        });
    });
})();
