from django.urls import path

from .views import store_docs_search, upload_store_documents_async

urlpatterns = [
    path(
        "documents/store/upload/",
        upload_store_documents_async,
        name="upload_store_documents",
    ),
    path("documents/search/store/", store_docs_search,
         name="store_docs_search"),
]
