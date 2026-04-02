// Ensure the `mgt` proxy created in base.html is available and do not overwrite it here.
(function(){
    if (typeof window === 'undefined') return;
    try {
        if (!window.hasOwnProperty('mgt') || !window.mgt) {
            // Create a safe fallback; base.html will normally install a robust proxy.
            window.mgt = { clearMarks: function(){ return undefined; } };
        }
    } catch (e) {
        console.warn('mgt availability check failed', e);
    }
})();

// CSRF fetch wrapper: automatically add `X-CSRFToken` header from cookies
// for same-origin POST requests to satisfy Flask-WTF/CSRFProtect when using fetch.
(function(){
    if (typeof window === 'undefined' || !window.fetch) return;

    function getCookie(name) {
        const v = document.cookie.match('(?:^|; )' + name.replace(/([.$?*|{}()[]\\\/\\+^])/g, '\\$1') + '=([^;]*)');
        return v ? decodeURIComponent(v[1]) : null;
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = function(input, init) {
        try {
            const requestUrl = (typeof input === 'string') ? input : (input && input.url) || '';
            init = init || {};
            const method = (init.method || (typeof input !== 'string' && input && input.method) || 'GET').toUpperCase();
            // treat relative URLs as same-origin
            let isSameOrigin = false;
            try {
                if (requestUrl.startsWith('/') || requestUrl.startsWith(window.location.origin)) isSameOrigin = true;
                else {
                    const urlObj = new URL(requestUrl, window.location.href);
                    isSameOrigin = urlObj.origin === window.location.origin;
                }
            } catch (e) {
                isSameOrigin = true;
            }

            if (method === 'POST' && isSameOrigin) {
                // ensure headers exist
                if (!init.headers) init.headers = {};
                // normalize Headers object
                let headers = init.headers instanceof Headers ? init.headers : new Headers(init.headers || {});
                if (!headers.get('X-CSRFToken')) {
                    const token = getCookie('csrf_token') || getCookie('csrf_token');
                    if (token) headers.set('X-CSRFToken', token);
                }
                init.headers = headers;
                // default to same-origin credentials so cookies are sent
                if (!init.credentials) init.credentials = 'same-origin';
            }
        } catch (e) {
            console.warn('CSRF fetch wrapper error', e);
        }
        return originalFetch(input, init);
    };
})();

// Dark Mode Toggle Functionality
document.addEventListener('DOMContentLoaded', function() {
    // Create dark mode toggle button
    const toggleButton = document.createElement('button');
    toggleButton.className = 'dark-mode-toggle ms-2';
    toggleButton.innerHTML = '<i class="bi bi-moon-stars"></i>';
    toggleButton.title = 'Toggle Dark Mode';

    // Add to navbar
    const navbarNav = document.querySelector('.navbar-nav.ms-auto');
    if (navbarNav) {
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.appendChild(toggleButton);
        navbarNav.insertBefore(li, navbarNav.firstChild);
    }

    // Check for saved theme preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        toggleButton.innerHTML = '<i class="bi bi-sun"></i>';
        toggleButton.title = 'Switch to Light Mode';
    }

    // Toggle dark mode
    toggleButton.addEventListener('click', function() {
        document.body.classList.toggle('dark-mode');

        if (document.body.classList.contains('dark-mode')) {
            localStorage.setItem('theme', 'dark');
            toggleButton.innerHTML = '<i class="bi bi-sun"></i>';
            toggleButton.title = 'Switch to Light Mode';
        } else {
            localStorage.setItem('theme', 'light');
            toggleButton.innerHTML = '<i class="bi bi-moon-stars"></i>';
            toggleButton.title = 'Switch to Dark Mode';
        }
    });

    // Enhanced UI interactions
    // Add smooth scrolling to anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add loading animation to forms
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Processing...';
            }
        });
    });

    // Enhanced card hover effects
    document.querySelectorAll('.card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-4px)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // Auto-hide alerts after 5 seconds
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            if (alert.classList.contains('fade')) {
                alert.classList.remove('show');
                setTimeout(() => alert.remove(), 150);
            } else {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 300);
            }
        }, 5000);
    });
});