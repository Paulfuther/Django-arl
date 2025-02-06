import logging
import traceback
from django.http import JsonResponse

logger = logging.getLogger("django")

def trigger_error(request):
    """Triggers an internal server error (500) and logs full details without duplicate tracebacks."""
    try:
        raise ValueError("This is a test 500 internal server error.")
    except Exception as e:
        error_traceback = traceback.format_exc()  # ✅ Explicitly capture full traceback

        # ✅ Log the error once with full traceback
        logger.error(
            f"🚨 Internal Server Error at {request.path}\n"
            f"Error: {str(e)}\nTraceback:\n{error_traceback}",
            exc_info=False,  # 🚀 Prevents Django from adding duplicate traceback
        )

        # Return a structured 500 response
        return JsonResponse(
            {"error": "An unexpected error occurred. Check logs for details."},
            status=500
        )