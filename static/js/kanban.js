// Team Task Manager - Kanban Board & Drag-and-Drop (Stage 4)
(function () {
    'use strict';

    var sortableInstances = [];

    function getCsrfToken() {
        // Try reading from hx-headers on body
        var bodyHeaders = document.body.getAttribute('hx-headers');
        if (bodyHeaders) {
            try {
                var parsed = JSON.parse(bodyHeaders);
                if (parsed['X-CSRFToken']) {
                    return parsed['X-CSRFToken'];
                }
            } catch (e) {
                // ignore JSON parse error
            }
        }
        // Fallback to CSRF cookie
        var cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
        if (cookieMatch) {
            return cookieMatch[1];
        }
        // Fallback to form input
        var csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return csrfInput ? csrfInput.value : '';
    }

    function showToast(message, type) {
        if (window.ttm && typeof window.ttm.showToast === 'function') {
            window.ttm.showToast(message, type);
        } else {
            alert(message);
        }
    }

    // 1. View Preference & Switcher (Board vs List)
    function applyViewPreference() {
        var container = document.getElementById('tasks-view-container');
        if (!container) return;

        var userId = container.getAttribute('data-user-id') || 'guest';
        var storageKey = 'ttm_task_view_' + userId;
        var preferredView = localStorage.getItem(storageKey) || 'board'; // Default is board for new users

        setViewMode(preferredView, false);
    }

    function setViewMode(mode, save) {
        var container = document.getElementById('tasks-view-container');
        if (!container) return;

        var boardView = document.getElementById('kanban-board-view');
        var listView = document.getElementById('task-list-view');
        var boardBtn = document.getElementById('view-mode-board-btn');
        var listBtn = document.getElementById('view-mode-list-btn');
        var userId = container.getAttribute('data-user-id') || 'guest';

        if (mode === 'list') {
            if (boardView) boardView.classList.add('d-none');
            if (listView) listView.classList.remove('d-none');
            if (boardBtn) boardBtn.classList.remove('active');
            if (listBtn) listBtn.classList.add('active');
            if (save) localStorage.setItem('ttm_task_view_' + userId, 'list');
        } else {
            if (boardView) boardView.classList.remove('d-none');
            if (listView) listView.classList.add('d-none');
            if (boardBtn) boardBtn.classList.add('active');
            if (listBtn) listBtn.classList.remove('active');
            if (save) localStorage.setItem('ttm_task_view_' + userId, 'board');
        }
    }

    // 2. Helpers for optimistic UI updates
    function updateColumnCount(status, delta) {
        var badge = document.getElementById('column-count-' + status);
        if (badge) {
            var current = parseInt(badge.textContent.trim(), 10) || 0;
            var next = Math.max(0, current + delta);
            badge.textContent = next;
        }
    }

    function checkEmptyPlaceholders() {
        ['todo', 'in_progress', 'done'].forEach(function (st) {
            var list = document.getElementById('kanban-cards-' + st);
            var emptyEl = document.getElementById('kanban-empty-' + st);
            if (list && emptyEl) {
                var cardCount = list.querySelectorAll('.kanban-card').length;
                if (cardCount === 0) {
                    emptyEl.classList.remove('d-none');
                } else {
                    emptyEl.classList.add('d-none');
                }
            }
        });
    }

    function revertCardPosition(itemEl, fromList, oldIndex) {
        var children = Array.prototype.filter.call(fromList.children, function (el) {
            return !el.classList.contains('kanban-empty-placeholder');
        });
        if (oldIndex >= children.length) {
            fromList.appendChild(itemEl);
        } else {
            fromList.insertBefore(itemEl, children[oldIndex]);
        }
    }

    function updateCardStatusDropdown(cardEl, newStatus) {
        var dropdownBtn = cardEl.querySelector('.task-status-btn');
        if (dropdownBtn) {
            dropdownBtn.classList.remove('btn-secondary', 'btn-primary', 'btn-success');
            var label = 'To Do';
            if (newStatus === 'done') {
                dropdownBtn.classList.add('btn-success');
                label = 'Done';
            } else if (newStatus === 'in_progress') {
                dropdownBtn.classList.add('btn-primary');
                label = 'In Progress';
            } else {
                dropdownBtn.classList.add('btn-secondary');
            }
            dropdownBtn.textContent = label;
        }
        var menuItems = cardEl.querySelectorAll('.dropdown-item');
        menuItems.forEach(function (item) {
            var vals = item.getAttribute('hx-vals');
            if (vals && vals.indexOf(newStatus) !== -1) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    // 3. Initialize SortableJS
    function initSortable() {
        if (typeof Sortable === 'undefined') {
            return;
        }

        // Clean up previous instances if DOM was replaced
        sortableInstances.forEach(function (inst) {
            try {
                inst.destroy();
            } catch (e) {
                // ignore
            }
        });
        sortableInstances = [];

        var columnLists = document.querySelectorAll('.kanban-cards-list');
        columnLists.forEach(function (listEl) {
            var instance = Sortable.create(listEl, {
                group: 'kanban-board',
                animation: 150,
                ghostClass: 'kanban-ghost',
                chosenClass: 'kanban-chosen',
                dragClass: 'kanban-dragging',
                filter: '.kanban-card-disabled, .kanban-empty-placeholder',
                preventOnFilter: true,
                onMove: function (evt) {
                    if (evt.dragged.classList.contains('kanban-card-disabled')) {
                        return false;
                    }
                    if (evt.dragged.getAttribute('data-busy') === 'true') {
                        return false;
                    }
                    return true;
                },
                onEnd: function (evt) {
                    var itemEl = evt.item;
                    var fromList = evt.from;
                    var toList = evt.to;
                    var oldStatus = fromList.getAttribute('data-status');
                    var newStatus = toList.getAttribute('data-status');

                    // If dropped within same column or no status change
                    if (fromList === toList || oldStatus === newStatus) {
                        return;
                    }

                    // Double-submit protection
                    if (itemEl.getAttribute('data-busy') === 'true') {
                        revertCardPosition(itemEl, fromList, evt.oldIndex);
                        return;
                    }

                    // Client-side permission check
                    if (itemEl.classList.contains('kanban-card-disabled')) {
                        revertCardPosition(itemEl, fromList, evt.oldIndex);
                        showToast('Permission denied. You cannot change status of this task.', 'danger');
                        return;
                    }

                    var statusUrl = itemEl.getAttribute('data-status-url');
                    var csrfToken = getCsrfToken();

                    // Optimistic UI updates
                    itemEl.setAttribute('data-busy', 'true');
                    itemEl.classList.add('opacity-75');

                    updateColumnCount(oldStatus, -1);
                    updateColumnCount(newStatus, 1);
                    checkEmptyPlaceholders();

                    // Send POST request
                    fetch(statusUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-CSRFToken': csrfToken,
                            'X-TTM-Kanban-Drag': 'true',
                            'Accept': 'application/json, text/html'
                        },
                        body: 'status=' + encodeURIComponent(newStatus)
                    }).then(function (response) {
                        if (!response.ok) {
                            return response.text().then(function (text) {
                                throw new Error(text || ('Error ' + response.status));
                            });
                        }
                        return response.text();
                    }).then(function () {
                        // Success!
                        itemEl.removeAttribute('data-busy');
                        itemEl.classList.remove('opacity-75');
                        itemEl.setAttribute('data-status', newStatus);
                        updateCardStatusDropdown(itemEl, newStatus);
                    }).catch(function (err) {
                        // Rollback on 400/403/404/500 or network failure
                        itemEl.removeAttribute('data-busy');
                        itemEl.classList.remove('opacity-75');
                        revertCardPosition(itemEl, fromList, evt.oldIndex);
                        updateColumnCount(oldStatus, 1);
                        updateColumnCount(newStatus, -1);
                        checkEmptyPlaceholders();

                        var errorMsg = err.message || 'Failed to update task status.';
                        if (errorMsg.startsWith('<')) {
                            errorMsg = 'Permission denied or invalid status change.';
                        }
                        showToast(errorMsg, 'danger');
                    });
                }
            });
            sortableInstances.push(instance);
        });
    }

    // 4. Main Init
    function initKanban() {
        applyViewPreference();
        initSortable();
        checkEmptyPlaceholders();
    }

    // Global event listeners
    document.addEventListener('DOMContentLoaded', function () {
        initKanban();
    });

    document.addEventListener('htmx:afterSwap', function (evt) {
        var target = evt.detail.target;
        if (target && (target.id === 'tasks-view-container' || target.id === 'task-list-container' || target.closest('#kanban-board-view'))) {
            initKanban();
        }
    });

    // Handle Quick Add form reset and collapse on successful task creation
    document.addEventListener('htmx:afterRequest', function (evt) {
        var xhr = evt.detail.xhr;
        var elt = evt.detail.elt;
        if (elt && elt.closest('.kanban-quick-add-form') && xhr && xhr.status >= 200 && xhr.status < 300) {
            var form = elt.closest('form');
            if (form) {
                var titleInput = form.querySelector('.quick-add-title-input');
                if (titleInput) {
                    titleInput.value = '';
                }
                var container = form.closest('.kanban-quick-add-form');
                if (container) {
                    container.classList.add('d-none');
                }
                var status = form.querySelector('input[name="status"]');
                if (status) {
                    var toggleBtn = document.querySelector('.btn-toggle-quick-add[data-status="' + status.value + '"]');
                    if (toggleBtn) {
                        toggleBtn.classList.remove('d-none');
                    }
                }
            }
        }
    });

    // View Switcher clicks
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('#task-view-switcher button');
        if (btn) {
            var view = btn.getAttribute('data-view');
            if (view) {
                setViewMode(view, true);
            }
            return;
        }

        // Toggle Quick Add form
        var toggleQuickAdd = e.target.closest('.btn-toggle-quick-add');
        if (toggleQuickAdd) {
            var st = toggleQuickAdd.getAttribute('data-status');
            var formEl = document.getElementById('quick-add-form-' + st);
            if (formEl) {
                formEl.classList.remove('d-none');
                toggleQuickAdd.classList.add('d-none');
                var input = formEl.querySelector('.quick-add-title-input');
                if (input) {
                    input.focus();
                }
            }
            return;
        }

        // Cancel Quick Add form
        var cancelQuickAdd = e.target.closest('.btn-cancel-quick-add');
        if (cancelQuickAdd) {
            var cancelStatus = cancelQuickAdd.getAttribute('data-status');
            var formBox = document.getElementById('quick-add-form-' + cancelStatus);
            if (formBox) {
                formBox.classList.add('d-none');
                var btnShow = document.querySelector('.btn-toggle-quick-add[data-status="' + cancelStatus + '"]');
                if (btnShow) {
                    btnShow.classList.remove('d-none');
                }
            }
            return;
        }
    });
})();
