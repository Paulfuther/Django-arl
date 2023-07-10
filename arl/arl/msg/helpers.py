import os
import sendgrid
from sendgrid.helpers.mail import Mail


def send_welcome_email(email):
    sg = sendgrid.SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
    from_email = os.environ.get('MAIL_DEFAULT_SENDER')

    message = Mail(
        from_email=from_email, 
        to_emails=email,
        subject="welcome aboard",     
    )

    message.template_id = os.environ.get('SENDGRID_NEWHIRE_ID')

    try:
        print(from_email, sg)
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
    except Exception as e:
        print(str(e))