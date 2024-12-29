from __future__ import absolute_import, unicode_literals

from datetime import datetime

from celery.utils.log import get_task_logger

from arl.celery import app
from arl.msg.helpers import create_master_email, create_hr_newhire_email
from arl.msg.models import EmailTemplate
from arl.user.models import CustomUser, Employer, UserManager

logger = get_task_logger(__name__)


@app.task(name="send_newhire_template_email")
def send_newhire_template_email_task(user_email, user_first_name,
                                     sendgrid_id, attachments=None):
    try:
        # Retrieve the template name based on the sendgrid_id
        template = EmailTemplate.objects.get(sendgrid_id=sendgrid_id)
        template_name = template.name
        create_master_email(user_email, user_first_name,
                            sendgrid_id, attachments)

        return f"Template '{template_name}' Emails Sent Successfully"

    except Exception as e:
        return str(e)


@app.task(name="create_hr_newhire_email")
def create_newhire_data_email(**email_data):
    try:
        create_hr_newhire_email(**email_data)
        logger.info(
            f"New hire email created successfully for "
            f"{email_data['email']}"
        )
        return (
            f"New hire email for {email_data['firstname']} - "
            f"{email_data['lastname']} created successfully"
        )
    except Exception as e:
        logger.error(
            f"Error creating new hire email "
            f"for {email_data['email']}: {str(e)}"
        )
        return f"Error creating new hire email: {str(e)}"


@app.task(name="save_user_to_db")
def save_user_to_db(**kwargs):
    try:
        # Create a new CustomUser object and save it to the database
        # Access the serialized data from kwargs
        employer_pk = kwargs.get("employer")
        manager_dropdown_pk = kwargs.get("manager_dropdown")
        dob_isoformat = kwargs.get("dob")
        manager_id = kwargs.get("manager_id")
        # Deserialize the data if needed
        # Convert employer_pk, manager_dropdown_pk, and dob_isoformat back
        # to their original types
        # Perform the necessary processing with the data
        # Update UserManager with user and manager, etc.
        # Example:
        user = CustomUser.objects.get(pk=kwargs["user_id"])
        user.employer = Employer.objects.get(pk=employer_pk)
        user.manager = CustomUser.objects.get(pk=manager_dropdown_pk)
        user.dob = datetime.strptime(dob_isoformat, "%Y-%m-%d").date()
        user.save()
        # Create a new UserManager object to associate
        # the user with the manager
        UserManager.objects.create(user=user, manager_id=manager_id)
    except Exception as e:
        # Handle any exceptions that may occur during database save
        print(f"An error occurred during database save: {e}")
