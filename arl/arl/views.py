from django.shortcuts import render


def error_403(request, exception):
    data = {}
    return render(request, 'incident/403.html', data)


def error_500(request, exception=None):
    data = {}
    return render(request, 'incident/500.html', data)


def custom_405(request, exception):
    """Return a custom response for 405 Method Not Allowed errors."""
    return render(request, 'incident/405.html', status=405)
