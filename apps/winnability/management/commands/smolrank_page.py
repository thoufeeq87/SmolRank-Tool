from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils.text import slugify

from apps.winnability.exceptions import SmolRankAPIError
from apps.winnability.services.analyzer import check_keyword


class Command(BaseCommand):
    help = "Check a keyword with SmolRank and generate an HTML results page."

    def add_arguments(self, parser):
        parser.add_argument("keyword", help="YouTube keyword to check (quote multi-word keywords)")
        parser.add_argument(
            "-o", "--output", help="Output HTML path (default: smolrank_<keyword>.html)"
        )

    def handle(self, *args, **options):
        try:
            result = check_keyword(options["keyword"])
        except SmolRankAPIError as exc:
            raise CommandError(str(exc))

        path = Path(options["output"] or f"smolrank_{slugify(options['keyword']) or 'keyword'}.html")
        path.write_text(render_to_string("winnability/report.html", {"result": result, "keyword": options["keyword"].strip(), "static_report": True}), encoding="utf-8")

        verdict = "Winnable" if result.winnable else "Tough"
        self.stdout.write(
            f"{verdict}: {len(result.small_channels)} of the top {result.total} channels "
            f"have under {result.threshold} subscribers"
        )
        self.stdout.write(self.style.SUCCESS(f"Results page written to {path.resolve()}"))
