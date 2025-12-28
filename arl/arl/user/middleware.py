import traceback

from django.http import HttpResponse

from .models import ErrorLog


class ErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, Exception):
            path = request.path
            method = request.method
            status_code = 500
            error_message = traceback.format_exc()

            # Save the error log to the database
            ErrorLog.objects.create(
                path=path,
                method=method,
                status_code=status_code,
                error_message=error_message,
            )
            return HttpResponse(
                "An error occurred. Please try again later.", status=status_code
            )
