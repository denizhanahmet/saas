// Main JavaScript for Appointment System

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            if (alert.classList.contains('alert-success') || alert.classList.contains('alert-info')) {
                var bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        });
    }, 5000);

    // Form validation enhancements
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Confirmation dialogs for delete actions
    var deleteButtons = document.querySelectorAll('.btn-danger[data-confirm]');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            var message = this.getAttribute('data-confirm') || 'Bu işlemi gerçekleştirmek istediğinizden emin misiniz?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // Real-time form validation
    var requiredFields = document.querySelectorAll('input[required], select[required], textarea[required]');
    requiredFields.forEach(function(field) {
        field.addEventListener('blur', function() {
            validateField(this);
        });

        field.addEventListener('input', function() {
            if (this.classList.contains('is-invalid')) {
                validateField(this);
            }
        });
    });

    // Date input restrictions
    var dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(function(input) {
        // Set minimum date to today if not already set
        if (!input.min) {
            var today = new Date().toISOString().split('T')[0];
            input.min = today;
        }

        // Validate date on change
        input.addEventListener('change', function() {
            if (this.value && this.value < this.min) {
                this.setCustomValidity('Geçmiş tarih seçilemez');
            } else {
                this.setCustomValidity('');
            }
        });
    });

    // Time input validation
    var timeInputs = document.querySelectorAll('input[type="time"]');
    timeInputs.forEach(function(input) {
        input.addEventListener('change', function() {
            validateTime(this);
        });
    });

    // Character counter for textareas
    var textareas = document.querySelectorAll('textarea[maxlength]');
    textareas.forEach(function(textarea) {
        var maxLength = textarea.getAttribute('maxlength');
        var counter = document.createElement('small');
        counter.className = 'form-text text-muted character-counter';
        textarea.parentNode.appendChild(counter);

        function updateCounter() {
            var remaining = maxLength - textarea.value.length;
            counter.textContent = remaining + ' karakter kaldı';

            if (remaining < 10) {
                counter.className = 'form-text text-danger character-counter';
            } else if (remaining < 50) {
                counter.className = 'form-text text-warning character-counter';
            } else {
                counter.className = 'form-text text-muted character-counter';
            }
        }

        textarea.addEventListener('input', updateCounter);
        updateCounter();
    });

    // Search functionality
    var searchInputs = document.querySelectorAll('input[type="search"]');
    searchInputs.forEach(function(input) {
        var timeout;
        input.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                // Perform search
                var form = input.closest('form');
                if (form) {
                    form.submit();
                }
            }, 500);
        });
    });

    // Sortable tables
    var tables = document.querySelectorAll('table[data-sortable]');
    tables.forEach(function(table) {
        var headers = table.querySelectorAll('th[data-sort]');
        headers.forEach(function(header) {
            header.style.cursor = 'pointer';
            header.addEventListener('click', function() {
                sortTable(table, this);
            });
        });
    });

    /*// Loading states for buttons
    var submitButtons = document.querySelectorAll('button[type="submit"]');
    submitButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            if (this.closest('form').checkValidity()) {
                this.innerHTML = '<span class="loading"></span> Yükleniyor...';
                this.disabled = true;
            }
        });
    });*/
});

// Helper Functions

function validateField(field) {
    var isValid = field.checkValidity();

    if (isValid) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
    } else {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
    }

    return isValid;
}

function validateTime(timeInput) {
    var time = timeInput.value;
    if (!time) return true;

    var [hours, minutes] = time.split(':').map(Number);
    var now = new Date();
    var selectedTime = new Date();
    selectedTime.setHours(hours, minutes, 0, 0);

    // Check if time is in the past for today
    if (timeInput.form.querySelector('input[type="date"]')) {
        var dateInput = timeInput.form.querySelector('input[type="date"]');
        if (dateInput.value === new Date().toISOString().split('T')[0]) {
            if (selectedTime < now) {
                timeInput.setCustomValidity('Geçmiş saat seçilemez');
                return false;
            }
        }
    }

    timeInput.setCustomValidity('');
    return true;
}

function sortTable(table, header) {
    var tbody = table.querySelector('tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var column = parseInt(header.getAttribute('data-sort'));
    var ascending = header.getAttribute('data-order') !== 'asc';

    rows.sort(function(a, b) {
        var aVal = a.cells[column].textContent.trim();
        var bVal = b.cells[column].textContent.trim();

        // Try to parse as numbers
        var aNum = parseFloat(aVal);
        var bNum = parseFloat(bVal);

        if (!isNaN(aNum) && !isNaN(bNum)) {
            return ascending ? aNum - bNum : bNum - aNum;
        } else {
            // String comparison
            return ascending ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        }
    });

    // Update table
    rows.forEach(function(row) {
        tbody.appendChild(row);
    });

    // Update header order
    var headers = table.querySelectorAll('th[data-sort]');
    headers.forEach(function(h) {
        h.removeAttribute('data-order');
    });
    header.setAttribute('data-order', ascending ? 'asc' : 'desc');

    // Update sort indicators
    headers.forEach(function(h) {
        h.innerHTML = h.innerHTML.replace(/ ↑| ↓/g, '');
    });
    header.innerHTML += ascending ? ' ↑' : ' ↓';
}

// AJAX Helper Functions
function makeRequest(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const config = {
        ...defaultOptions,
        ...options
    };

    return fetch(url, config)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .catch(error => {
            console.error('Request failed:', error);
            throw error;
        });
}

// Utility Functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('tr-TR');
}

function formatTime(timeString) {
    const [hours, minutes] = timeString.split(':');
    return `${hours}:${minutes}`;
}

function formatDateTime(dateString, timeString) {
    return `${formatDate(dateString)} ${formatTime(timeString)}`;
}

// Export functions for use in other scripts
window.AppointmentSystem = {
    validateField,
    validateTime,
    makeRequest,
    formatDate,
    formatTime,
    formatDateTime
};