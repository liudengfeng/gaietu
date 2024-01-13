STYLE = """
<style>

button {
    border: none; /* 无边框 */
    height: 40px;
    margin-left: 5px;
    margin-right: 5px;
    margin-top: 20px;
    margin-bottom: 20px;
}

.text-decoration-underline {
    text-decoration: underline;
}

.text-decoration-line-through {
    text-decoration: line-through;
}

.text-decoration-wavy-underline {
    text-decoration: underline wavy;
    text-decoration-color: purple;
}

.btn-primary {
    color: #fff;
    background-color: #007bff;
    border-color: #007bff;
}

.btn-secondary {
    color: #fff;
    background-color: #6c757d;
    border-color: #6c757d;
}

.btn-success {
    color: #fff;
    background-color: #28a745;
    border-color: #28a745;
}

.btn-danger {
    color: #fff;
    background-color: #dc3545;
    border-color: #dc3545;
}

.btn-warning {
    color: #212529;
    background-color: #ffc107;
    border-color: #ffc107;
}

.btn-info {
    color: #fff;
    background-color: #17a2b8;
    border-color: #17a2b8;
}

.btn-light {
    color: #212529;
    background-color: #f8f9fa;
    border-color: #f8f9fa;
}

.btn-dark {
    color: #fff;
    background-color: #343a40;
    border-color: #343a40;
}

.tippy-tooltip.tomato-theme {
    background-color: #28a745; /* Bootstrap Success color */
    color: #ffffff; /* White color for text */
}

</style>
"""

TIPPY_JS = """
<script src="https://unpkg.com/popper.js@1"></script>
<script src="https://unpkg.com/tippy.js@5"></script>
<script>
    tippy('[data-tippy-content]', {
        allowHTML: true,
        theme: 'tomato',
    });
</script>
"""
