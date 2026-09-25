// JavaScript for Online Parking Slot Reservation System & Animations

document.addEventListener('DOMContentLoaded', function() {
    // -------------------------------------------------------------------------
    // App Launch Vehicle Splash Screen Handler
    // -------------------------------------------------------------------------
    const splashScreen = document.getElementById('app-splash-screen');
    const splashBar = document.getElementById('splashProgressBar');
    const splashTarget = document.querySelector('.splash-parking-target');

    if (splashScreen) {
        const hasSeenSplash = sessionStorage.getItem('parkease_splash_session');

        const dismissSplash = () => {
            if (splashTarget) splashTarget.classList.add('parked');
            if (splashBar) splashBar.style.width = '100%';
            setTimeout(() => {
                splashScreen.classList.add('hide-splash');
                sessionStorage.setItem('parkease_splash_session', 'true');
            }, 250);
        };

        // Tap anywhere to skip instantly
        splashScreen.addEventListener('click', dismissSplash);

        if (!hasSeenSplash) {
            // Animate progress bar fill
            setTimeout(() => {
                if (splashBar) splashBar.style.width = '100%';
            }, 60);

            // Car reaches target bay -> illuminate bay & pop green checkmark
            setTimeout(() => {
                if (splashTarget) splashTarget.classList.add('parked');
            }, 850);

            // Auto smooth exit transition
            setTimeout(() => {
                splashScreen.classList.add('hide-splash');
                sessionStorage.setItem('parkease_splash_session', 'true');
            }, 1450);
        } else {
            // Fast fade if already seen in current browsing session
            splashScreen.classList.add('hide-splash');
        }
    }

    // Page Transition Progress Indicator Completion
    const progressBar = document.getElementById('app-page-progress');
    if (progressBar) {
        progressBar.classList.add('done');
        setTimeout(() => {
            progressBar.classList.remove('done', 'loading');
            progressBar.style.width = '0%';
        }, 500);
    }

    // Smooth Page Navigation Interception (App-like feel)
    const links = document.querySelectorAll('a[href]:not([target="_blank"]):not([href^="#"]):not([href^="javascript"]):not([href^="mailto:"]):not([href^="tel:"])');
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (!href || href.startsWith('#') || this.hasAttribute('download') || this.hasAttribute('data-bs-toggle') || this.hasAttribute('data-bs-target')) {
                return;
            }

            // If same page anchor or modifier keys, skip
            if (e.metaKey || e.ctrlKey || e.shiftKey) return;

            // Trigger top glowing transition progress
            if (progressBar) {
                progressBar.style.width = '0%';
                progressBar.classList.remove('done');
                progressBar.classList.add('loading');
            }

            // Smooth exit transition
            const mainContent = document.querySelector('.main-content');
            if (mainContent && !document.startViewTransition) {
                mainContent.style.transition = 'opacity 0.18s ease, transform 0.18s ease';
                mainContent.style.opacity = '0.4';
                mainContent.style.transform = 'scale(0.995)';
            }
        });
    });

    // Form submission transition
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            if (progressBar) {
                progressBar.style.width = '0%';
                progressBar.classList.remove('done');
                progressBar.classList.add('loading');
            }
        });
    });

    // Auto upper-case vehicle numbers and booking IDs
    const upperInputs = document.querySelectorAll('input.text-uppercase');
    upperInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    });

    // Auto set minimum date to today for date inputs
    const dateInputs = document.querySelectorAll('input[type="date"]');
    const today = new Date().toISOString().split('T')[0];
    dateInputs.forEach(input => {
        if (!input.getAttribute('min')) {
            input.setAttribute('min', today);
        }
    });

    // Payment method tabs / UI toggles
    const paymentRadios = document.querySelectorAll('input[name="payment_method"]');
    const upiDetails = document.getElementById('upi-details');
    const cardDetails = document.getElementById('card-details');
    const cashDetails = document.getElementById('cash-details');

    function updatePaymentView() {
        const selected = document.querySelector('input[name="payment_method"]:checked');
        if (!selected) return;

        if (upiDetails) upiDetails.style.display = selected.value === 'UPI' ? 'block' : 'none';
        if (cardDetails) cardDetails.style.display = selected.value === 'CARD' ? 'block' : 'none';
        if (cashDetails) cashDetails.style.display = selected.value === 'CASH' ? 'block' : 'none';
    }

    if (paymentRadios.length > 0) {
        paymentRadios.forEach(radio => {
            radio.addEventListener('change', updatePaymentView);
        });
        updatePaymentView();
    }

    // Vehicle Type Animated Selector Handler
    const vehicleCards = document.querySelectorAll('.vehicle-select-card');
    vehicleCards.forEach(card => {
        card.addEventListener('click', function() {
            const parent = this.closest('.vehicle-selector-group');
            if (parent) {
                parent.querySelectorAll('.vehicle-select-card').forEach(c => c.classList.remove('active'));
            }
            this.classList.add('active');

            const vehicleType = this.getAttribute('data-vehicle');
            const targetId = this.getAttribute('data-target');
            if (targetId) {
                const targetInput = document.getElementById(targetId);
                if (targetInput) {
                    targetInput.value = vehicleType;
                }
            }

            // Micro haptic vibration animation on icon
            const icon = this.querySelector('.vehicle-card-icon i');
            if (icon) {
                icon.style.transform = 'scale(1.25)';
                setTimeout(() => {
                    icon.style.transform = '';
                }, 200);
            }
        });
    });

    // 1-Tap Quick Schedule Preset Handler
    const presetChips = document.querySelectorAll('.preset-chip');
    presetChips.forEach(chip => {
        chip.addEventListener('click', function() {
            const formId = this.getAttribute('data-form');
            const presetType = this.getAttribute('data-preset');
            const form = document.getElementById(formId);
            if (!form) return;

            const dateInput = form.querySelector('input[type="date"]');
            const timeInputs = form.querySelectorAll('input[type="time"]');
            if (!dateInput || timeInputs.length < 2) return;

            const startTimeInput = timeInputs[0];
            const endTimeInput = timeInputs[1];

            // Highlight chip
            form.querySelectorAll('.preset-chip').forEach(c => c.classList.remove('active'));
            this.classList.add('active');

            const now = new Date();
            const pad = (n) => String(n).padStart(2, '0');
            const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

            if (presetType === 'now') {
                dateInput.value = todayStr;
                const startDt = new Date(now.getTime() + 15 * 60000);
                const endDt = new Date(startDt.getTime() + 2 * 3600000);
                startTimeInput.value = `${pad(startDt.getHours())}:${pad(startDt.getMinutes())}`;
                endTimeInput.value = `${pad(endDt.getHours())}:${pad(endDt.getMinutes())}`;
            } else if (presetType === 'evening') {
                dateInput.value = todayStr;
                startTimeInput.value = '18:00';
                endTimeInput.value = '21:00';
            } else if (presetType === 'tomorrow') {
                const tomorrow = new Date(now.getTime() + 86400000);
                dateInput.value = `${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}`;
                startTimeInput.value = '09:00';
                endTimeInput.value = '12:00';
            }
        });
    });
});

