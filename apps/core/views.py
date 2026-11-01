"""Dev-only previews of the error pages (wired up in config/urls.py when DEBUG)."""
from django.http import Http404
from django.views.defaults import page_not_found, server_error


def preview_404(request):
    return page_not_found(request, Http404())


def preview_500(request):
    return server_error(request)
