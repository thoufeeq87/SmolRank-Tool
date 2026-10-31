from django.shortcuts import render

from .forms import KeywordForm
from .services.analyzer import check_keyword
from .services.exceptions import SmolRankError


def index(request):
    form = KeywordForm(request.GET or None)
    context = {"form": form}
    if form.is_valid():
        try:
            context["report"] = check_keyword(form.cleaned_data["keyword"])
        except SmolRankError as exc:
            context["error"] = str(exc)
    return render(request, "smolrank/index.html", context)
