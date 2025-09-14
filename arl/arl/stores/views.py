import math
import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.temp import NamedTemporaryFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from arl.dsign.models import SignedDocumentFile
from arl.user.models import Store

from .models import StoreDocumentJob
from .tasks import process_store_document_task


def _human_size(bytes_: int) -> str:
    """Return file size in KB or MB (rounded)."""
    if bytes_ < 1024:
        return f"{bytes_}B"
    elif bytes_ < 1024 * 1024:
        return f"{math.ceil(bytes_ / 1024)}KB"
    else:
        return f"{math.ceil(bytes_ / (1024 * 1024))}MB"


MAX_BYTES = 100 * 1024 * 1024  # 100 MB


def _save_to_temp(uploaded, suffix: str = "") -> str:
    ext = suffix or (os.path.splitext(getattr(uploaded, "name", ""))[1] or ".bin")
    tmp = NamedTemporaryFile(
        delete=False, dir=getattr(settings, "MEDIA_TMP", None), suffix=ext
    )
    if isinstance(uploaded, InMemoryUploadedFile):
        tmp.write(uploaded.read())
    else:
        for chunk in uploaded.chunks():
            tmp.write(chunk)
    tmp.flush()
    tmp.close()
    return tmp.name


@login_required
def upload_store_documents_async(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    employer = getattr(request.user, "employer", None)
    if not employer:
        return JsonResponse({"ok": False, "error": "No employer"}, status=403)

    store_id = request.POST.get("store_id")
    title = (request.POST.get("document_title") or "").strip()
    notes = (request.POST.get("notes") or "").strip()
    fileobj = request.FILES.get("file")
    if not store_id or not title or not fileobj:
        return JsonResponse(
            {"ok": False, "error": "Store, title, and file are required."}, status=400
        )

    if getattr(fileobj, "size", 0) > MAX_BYTES:
        return JsonResponse(
            {
                "ok": False,
                "error": f"File too large (max {MAX_BYTES // (1024 * 1024)}MB).",
            },
            status=400,
        )

    store = get_object_or_404(Store, pk=store_id, employer=employer)

    # Build final object key NOW (same as before)
    company = slugify(employer.name or "company")
    year, month = timezone.now().strftime("%Y"), timezone.now().strftime("%m")
    base, ext = os.path.splitext(fileobj.name or "")
    safe_title = slugify(title) or "document"
    unique_id = uuid.uuid4().hex[:8]
    final_ext = ext or ".bin"
    # human-readable size
    size_label = _human_size(fileobj.size)
    filename = f"{safe_title}-{size_label}-{unique_id}{final_ext}"
    object_key = f"DOCUMENTS/{company}/stores/{store.number or store.id}/{year}/{month}/{filename}"

    # 1) Create SDF row immediately (keeps old behavior)
    sdf = SignedDocumentFile.objects.create(
        user=request.user,
        store=store,
        employer=employer,
        envelope_id=uuid.uuid4().hex[:10],
        file_name=filename,
        file_path=object_key,
        document_title=title,
        notes=notes,
        is_company_document=True,
    )

    # 2) Save upload to temp, enqueue task
    tmp_path = _save_to_temp(fileobj, suffix=final_ext)
    job = StoreDocumentJob.objects.create(
        user=request.user,
        sdf_id=sdf.id,
        tmp_path=tmp_path,
        original_name=fileobj.name or filename,
        original_ct=(getattr(fileobj, "content_type", "") or ""),
        status="queued",
    )

    process_store_document_task.delay(str(job.id))

    messages.success(request, f"Uploaded '{title}' for {store.number}.")
    return redirect(f"{reverse('documents_dashboard')}?tab=store#tab-store")


@login_required
def store_docs_search(request):
    employer = getattr(request.user, "employer", None)
    if not employer:
        return render(
            request,
            "user/documents/partials/store_results.html",
            {"q": "", "stores_results": [], "store_documents": []},
        )

    q = (request.GET.get("q") or "").strip()
    stores_results, docs = [], []

    if q:
        stores_results = (
            Store.objects.filter(employer=employer)
            .filter(Q(number__icontains=q) | Q(city__icontains=q))
            .order_by("number")
        )
        docs = (
            SignedDocumentFile.objects.filter(
                employer=employer, store__in=stores_results
            )
            .select_related("store")
            .order_by("-uploaded_at")
        )

    return render(
        request,
        "user/documents/partials/store_results.html",
        {"q": q, "stores_results": stores_results, "docs": docs},
    )
