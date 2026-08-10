import importlib.metadata
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


IMPORTANT_PACKAGES = [
    "Django",
    "cryptography",
    "Pillow",
    "PyJWT",
    "urllib3",
    "tornado",
    "docusign-esign",
    "celery",
    "kombu",
]


class Command(BaseCommand):
    help = "Show DocketProof dependency and Python environment health."

    def handle(self, *args, **options):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("DocketProof Dependency Health"))
        self.stdout.write("=" * 40)

        self.stdout.write(f"Python: {sys.version.split()[0]}")
        self.stdout.write(f"Executable: {sys.executable}")
        self.stdout.write("")

        self.stdout.write(self.style.MIGRATE_HEADING("Important packages"))
        self.stdout.write("-" * 40)

        for package in IMPORTANT_PACKAGES:
            try:
                version = importlib.metadata.version(package)
                self.stdout.write(f"{package:<22} {version}")
            except importlib.metadata.PackageNotFoundError:
                self.stdout.write(
                    self.style.WARNING(f"{package:<22} NOT INSTALLED")
                )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Dependency integrity"))
        self.stdout.write("-" * 40)

        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
        )

        output = (result.stdout or result.stderr).strip()

        if result.returncode == 0:
            self.stdout.write(self.style.SUCCESS(f"PASS - {output}"))
        else:
            self.stdout.write(self.style.ERROR("FAIL"))
            self.stdout.write(output)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Requirements file"))
        self.stdout.write("-" * 40)

        # settings.BASE_DIR is docketproof/arl in this project.
        requirements_file = Path(settings.BASE_DIR).parent.parent / "requirements.txt"

        if requirements_file.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"PASS - requirements.txt found at {requirements_file}"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"FAIL - requirements.txt not found at {requirements_file}"
                )
            )

        self.stdout.write("")