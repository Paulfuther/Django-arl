from __future__ import absolute_import, unicode_literals

import json
from datetime import datetime

from celery.utils.log import get_task_logger

from arl.celery import app
from arl.msg.helpers import create_master_email
from arl.user.models import CustomUser, Employer

logger = get_task_logger(__name__)


# Works
@app.task(name="send_newhire_template_email")
def send_newhire_template_email_task(
    to_email, sendgrid_id, template_data, attachments=None
):
    """
    Celery task to send an email using SendGrid.
    """
    try:
        # Ensure template_data is a dictionary
        if not isinstance(template_data, dict):
            raise ValueError(
                f"❌ Expected dictionary for template_data, got {type(template_data)}"
            )

        senior_contact_name = template_data.get("senior_contact_name", "HR Team")

        print(f"📧 Sending New Hire Email to: {to_email}")
        print(f"📜 Senior Contact Name: {senior_contact_name}")
        print(f"📜 Email Template Data: {template_data}")

        # Call the helper function, passing template_data
        create_master_email(
            to_email=to_email,
            sendgrid_id=sendgrid_id,
            template_data=template_data,  # ✅ Pass template data
            attachments=attachments,
        )
    except Exception as e:
        print(f"Error in send_master_email_task: {e}")
    return False


@app.task(name="create_hr_newhire_email")
def create_newhire_data_email(email_data):
    try:
        logger.info("📩 New hire data email task started")
        logger.debug(f"Raw email data: {email_data}")

        # Handle stringified input
        if isinstance(email_data, str):
            email_data = json.loads(email_data)

        employer_id = email_data.get("employer_id")
        if not employer_id:
            raise ValueError("Missing employer_id in email data")

        employer = Employer.objects.filter(id=employer_id).first()
        if not employer:
            raise ValueError(f"No employer found with ID {employer_id}")

        email_data["company_name"] = employer.name

        # ✅ Get active users in the correct employer and group
        hr_users = CustomUser.objects.filter(
            is_active=True, employer_id=employer_id, groups__name="new_hire_data_email"
        )

        to_emails = [user.email for user in hr_users]
        # 🔁 Fallback to employer email if none found
        if not to_emails:
            if employer.email:
                logger.warning(
                    f"⚠️ No HR users found. Falling back to employer email: {employer.email}"
                )
                to_emails = [employer.email]
            else:
                error_msg = f"❌ No HR or fallback email for employer ID {employer_id}"
                logger.error(error_msg)
                return error_msg

        # ✅ Send via Master Email Function
        create_master_email(
            to_email=to_emails,
            sendgrid_id="d-d0806dff1e62449d9ba8cfcb481accaa",
            template_data=email_data,
        )

        logger.info(
            f"New hire email created successfully for {email_data.get('email')}"
        )
        return (
            f"New hire email for {email_data.get('firstname')} - "
            f"{email_data.get('lastname')} created successfully"
        )

    except Exception as e:
        logger.error(
            f"Error creating new hire email for {email_data.get('email')}: {str(e)}"
        )
        return f"Error creating new hire email: {str(e)}"


@app.task(name="save_user_to_db")
def save_user_to_db(**kwargs):
    try:
        # Create a new CustomUser object and save it to the database
        # Access the serialized data from kwargs
        employer_pk = kwargs.get("employer")
        dob_isoformat = kwargs.get("dob")
        user = CustomUser.objects.get(pk=kwargs["user_id"])
        user.employer = Employer.objects.get(pk=employer_pk)
        user.dob = datetime.strptime(dob_isoformat, "%Y-%m-%d").date()
        # ✅ Convert and assign SIN Expiration Date if it exists
        sin_expiration_date = kwargs.get("sin_expiration_date")
        if sin_expiration_date:
            user.sin_expiration_date = datetime.fromisoformat(
                sin_expiration_date
            ).date()

        # ✅ Convert and assign Work Permit Expiration Date if it exists
        work_permit_expiration_date = kwargs.get("work_permit_expiration_date")
        if work_permit_expiration_date:
            user.work_permit_expiration_date = datetime.fromisoformat(
                work_permit_expiration_date
            ).date()
        # Deserialize the data if needed
        # Convert employer_pk, manager_dropdown_pk, and dob_isoformat back
        # to their original types
        # Perform the necessary processing with the data
        # Update UserManager with user and manager, etc.
        # Example:
        user.save()
    except Exception as e:
        # Handle any exceptions that may occur during database save
        print(f"An error occurred during database save: {e}")


@app.task(name="send_payment_email")
def send_payment_email_task(to_email, payment_link, employer_name):
    """Send an email with the Stripe payment link using the master email function."""
    sendgrid_id = (
        "d-e31a2d72f8b145de98ba8d9fa267bc04"  # 🔹 Use your SendGrid template ID
    )
    try:
        # ✅ Use the employer name passed from the approval process
        template_data = {
            "payment_link": payment_link,
            "name": employer_name,  # ✅ Ensure we use the correct employer name
            "subject": "Complete Your Registration - Payment Required",
            "body": f"'{payment_link}'",
        }

        # ✅ Call the master email function
        return create_master_email(to_email, sendgrid_id, template_data)

    except Exception as e:
        print(f"❌ Error sending payment email: {str(e)}")
        return False
