// Team Task Manager - Frontend Application Logic
(function () {
    'use strict';

    // Disable eval in HTMX for strict Content Security Policy (CSP) compatibility
    if (window.htmx) {
        window.htmx.config.allowEval = false;
    }

    // Helper to display dismissible Bootstrap toasts without inline eval
    function showToast(message, type) {
        var container = document.getElementById('ttm-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'ttm-toast-container';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1090';
            document.body.appendChild(container);
        }

        var toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center text-bg-' + (type || 'danger') + ' border-0 show shadow';
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');

        var dFlex = document.createElement('div');
        dFlex.className = 'd-flex';

        var toastBody = document.createElement('div');
        toastBody.className = 'toast-body';
        toastBody.textContent = message;

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'btn-close btn-close-white me-2 m-auto';
        closeBtn.setAttribute('aria-label', 'Close');
        closeBtn.addEventListener('click', function () {
            toastEl.remove();
        });

        dFlex.appendChild(toastBody);
        dFlex.appendChild(closeBtn);
        toastEl.appendChild(dFlex);
        container.appendChild(toastEl);

        setTimeout(function () {
            if (toastEl.parentNode) {
                toastEl.remove();
            }
        }, 5000);
    }

    // Handle HTMX response errors (400, 403, 404, 500)
    document.addEventListener('htmx:responseError', function (evt) {
        var xhr = evt.detail.xhr;
        var status = xhr ? xhr.status : 0;
        var responseText = xhr && xhr.responseText ? xhr.responseText.trim() : '';
        var msg = responseText;

        // If response is HTML (e.g. Django default error pages), use clean user-friendly text
        if (!msg || msg.startsWith('<')) {
            if (status === 403) {
                msg = 'Permission denied. You do not have permission to perform this action.';
            } else if (status === 400) {
                msg = 'Invalid request. Please check your input and try again.';
            } else if (status === 404) {
                msg = 'The requested resource was not found.';
            } else if (status >= 500) {
                msg = 'A server error occurred. Please try again later.';
            } else {
                msg = 'Request failed with status ' + status + '.';
            }
        }
        showToast(msg, 'danger');
    });

    // Handle HTMX network errors
    document.addEventListener('htmx:sendError', function () {
        showToast('Network error. Please check your connection.', 'danger');
    });

    // Synchronously reset filter form controls when Clear is clicked
    document.addEventListener('click', function (e) {
        var clearBtn = e.target.closest('.btn-clear-filters');
        if (clearBtn) {
            var form = document.getElementById('task-filter-form');
            if (form) {
                form.reset();
                var searchInput = form.querySelector('input[name="search"]');
                if (searchInput) {
                    searchInput.value = '';
                }
                var selects = form.querySelectorAll('select');
                selects.forEach(function (sel) {
                    if (sel.name === 'is_archived') {
                        sel.value = '0';
                    } else {
                        sel.value = '';
                    }
                });
            }
        }
    });
})();
