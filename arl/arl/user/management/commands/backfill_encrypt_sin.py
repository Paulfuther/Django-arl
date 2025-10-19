# arl/user/management/commands/backfill_encrypt_sin.py
from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps
from django.db import transaction

# Use your crypto helpers
from arl.utils.crypto import normalize_digits, sin_encrypt, sin_last4, sin_hash
try:
    from arl.utils.crypto import sin_luhn_valid  # optional, if present
except Exception:
    def sin_luhn_valid(s: str) -> bool:
        d = "".join(ch for ch in s or "" if ch.isdigit())
        if len(d) != 9:
            return False
        total = 0
        for i, ch in enumerate(d):
            n = int(ch)
            if (i % 2) == 1:
                n *= 2
                total += (n // 10) + (n % 10)
            else:
                total += n
        return (total % 10) == 0


class Command(BaseCommand):
    help = (
        "Backfill encryption for existing plaintext SINs into "
        "sin_encrypted / sin_last4 / sin_hash."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--chunk-size", type=int, default=500,
            help="Batch size for updates (default: 500)"
        )
        parser.add_argument(
            "--validate-luhn", action="store_true",
            help="Validate SIN with Luhn before encrypting; skip invalids"
        )
        parser.add_argument(
            "--from-plaintext-only", action="store_true",
            help="Only process rows where the old plaintext 'sin' column is non-empty"
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Do not write changes; just report what would happen"
        )
        parser.add_argument(
            "--verbose", action="store_true",
            help="Print each updated user id"
        )

    def handle(self, *args, **opts):
        chunk = opts["chunk_size"]
        validate_luhn = opts["validate_luhn"]
        from_plaintext_only = opts["from_plaintext_only"]
        dry_run = opts["dry_run"]
        very_verbose = opts["verbose"]

        # Resolve the actual user model from AUTH_USER_MODEL
        app_label, model_name = settings.AUTH_USER_MODEL.split(".")
        User = apps.get_model(app_label, model_name)

        # Build base queryset
        qs = User.objects.all().only("id", "sin_encrypted", "sin_last4", "sin_hash")

        # Determine source of plaintext: prefer old `sin` column if present,
        # otherwise try to use decrypted value from a property if you have one.
        has_plaintext_column = "sin" in [f.name for f in User._meta.get_fields()]
        if has_plaintext_column and from_plaintext_only:
            qs = qs.exclude(sin__isnull=True).exclude(sin="")

        total = qs.count()
        self.stdout.write(self.style.NOTICE(f"Scanning {total} user rows..."))

        processed = 0
        updated = 0
        skipped_luhn = 0
        already_done = 0
        missing_plaintext = 0

        # Iterate in id order for stability
        base = qs.order_by("id").values_list("id", flat=True)
        ids = list(base)

        for start in range(0, len(ids), chunk):
            batch_ids = ids[start:start+chunk]
            # Load full rows for this chunk
            rows = list(
                User.objects.filter(id__in=batch_ids)
                .only("id", "sin_encrypted", "sin_last4", "sin_hash", *(["sin"] if has_plaintext_column else []))
            )

            to_update = []
            for u in rows:
                processed += 1

                # If already has encrypted data, skip
                if u.sin_encrypted:
                    already_done += 1
                    if very_verbose:
                        self.stdout.write(f"skip (already encrypted) id={u.id}")
                    continue

                # 1) Try old plaintext column
                plaintext = None
                if has_plaintext_column:
                    plaintext = getattr(u, "sin", None)

                # 2) If no old column (or empty), nothing we can do automatically
                if not plaintext:
                    missing_plaintext += 1
                    if very_verbose:
                        self.stdout.write(f"skip (no plaintext) id={u.id}")
                    continue

                digits = normalize_digits(plaintext)
                if not digits:
                    missing_plaintext += 1
                    if very_verbose:
                        self.stdout.write(f"skip (no digits) id={u.id}")
                    continue

                if validate_luhn and not sin_luhn_valid(digits):
                    skipped_luhn += 1
                    if very_verbose:
                        self.stdout.write(f"skip (luhn invalid) id={u.id} value={digits}")
                    continue

                # Set encrypted fields on the instance
                u.sin_encrypted = sin_encrypt(digits)
                u.sin_last4 = sin_last4(digits)
                u.sin_hash = sin_hash(digits)
                to_update.append(u)

            if to_update and not dry_run:
                with transaction.atomic():
                    User.objects.bulk_update(
                        to_update, ["sin_encrypted", "sin_last4", "sin_hash"], batch_size=chunk
                    )
                updated += len(to_update)

            # progress line
            self.stdout.write(
                f"Processed {processed}/{total} | updated {updated} | "
                f"already {already_done} | luhn-skip {skipped_luhn} | missing {missing_plaintext}"
            )

        # Final summary
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no database changes were written."))
        self.stdout.write(self.style.SUCCESS(
            f"Done. updated={updated}, already={already_done}, "
            f"luhn_skipped={skipped_luhn}, missing_plaintext={missing_plaintext}, scanned={processed}"
        ))