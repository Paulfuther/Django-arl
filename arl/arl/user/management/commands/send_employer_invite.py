from django.core.management.base import BaseCommand
from arl.user.models import Employer, NewHireInvite
from arl.msg.helpers import create_master_email
from django.conf import settings
from django.utils.crypto import get_random_string


class Command(BaseCommand):
    help = "Simulates Stripe webhook to send employer invite email"

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="Employer email to simulate webhook")

    def handle(self, *args, **kwargs):
        email = kwargs["email"]
        employer = Employer.objects.filter(email=email).first()

        if employer:
            employer.is_active = True
            employer.subscription_id = "sub_test_12345"
            employer.save()
            self.stdout.write(self.style.SUCCESS(f"✅ Employer {employer.name} activated."))

            # ✅ Ensure an invite exists
            invite = NewHireInvite.objects.filter(email=email, used=False).first()
            if not invite:
                invite_token = get_random_string(64)
                invite = NewHireInvite.objects.create(
                    employer=employer,
                    email=email,
                    name=employer.name,
                    role="EMPLOYER",
                    token=invite_token
                )
                self.stdout.write(self.style.SUCCESS(f"📩 Invite Created! Use this link: /register/{invite.token}/"))

            invite_link = f"{settings.SITE_URL}/register/{invite.token}/"

            sendgrid_template_id = settings.SENDGRID_EMPLOYER_REGISTER_AS_USER

            email_data = {
                "to_email": employer.email,
                "sendgrid_id": sendgrid_template_id,
                "template_data": {
                    "employer_name": employer.name,
                    "invite_link": invite_link,
                    "sender_contact_name": "Support Team",
                },
                "verified_sender": employer.verified_sender_email,
            }

            create_master_email(**email_data)
            self.stdout.write(self.style.SUCCESS(f"✅ Employer invite sent to {employer.email}"))
        else:
            self.stdout.write(self.style.ERROR("⚠️ No employer found with that email."))