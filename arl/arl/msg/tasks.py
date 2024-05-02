from __future__ import absolute_import, unicode_literals

import csv
import os

import pandas as pd
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth.models import Group
from django.db import connection

from arl.celery import app
from arl.msg.helpers import create_single_csv_email, send_whats_app_template

logger = get_task_logger(__name__)


@app.task(name="send whatsapp")
def send_template_whatsapp_task(whatsapp_id, from_id, group_id):
    try:
        # Retrieve all users within the group
        print(whatsapp_id)
        group = Group.objects.get(pk=group_id)
        users_in_group = group.user_set.filter(is_active=True)
        # Retrieve the template name based on the whatsapp_id
        # template = WhatsAppTemplate.objects.get(whatsapp_id=whatsapp_id)
        # template_name = template.name
        for user in users_in_group:
            print(user.first_name, user.phone_number)
            send_whats_app_template(
                whatsapp_id, from_id, user.first_name, user.phone_number
            )

        return f"Whatsapp Template   Sent Successfully"

    except Exception as e:
        return str(e)


@app.task(name="tobacco csv report")
def generate_and_save_csv_report():
    sql_query = """
    SELECT * FROM msg_emailevent
    WHERE timestamp BETWEEN '2023-04-01' AND '2023-04-30'
    AND sg_template_name = 'Tobacco Compliance';
    """
    # Path where the CSV will be saved
    file_path = os.path.join(settings.MEDIA_ROOT, "monthly_report.csv")
    pivot_file_path = os.path.join(settings.MEDIA_ROOT, "monthly_pivot_report.csv")
    with connection.cursor() as cursor:
        cursor.execute(sql_query)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

        # Write to CSV file
        with open(file_path, "w", newline="") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(columns)  # write headers
            csvwriter.writerows(rows)

    # Read the CSV into a DataFrame
    df = pd.read_csv(file_path)
    print(df)
    # Create a pivot table
    pivot_table = pd.pivot_table(
        df,
        values='sg_event_id',
        index='email',
        columns='event',
        aggfunc='count',
        fill_value=0
    )
    
    # Save the pivot table to a new CSV file
    pivot_table.to_csv(pivot_file_path)

    # Send the email with the CSV attached
    email_sent = create_single_csv_email(
        to_email="paul.futher@gmail.com",
        subject="Monthly Tobacco Compliance Report",
        body="Attached is the monthly Tobacco Compliance report.",
        file_path=pivot_file_path,
    )

    if email_sent:
        return "Report generated and emailed successfully."
    else:
        return "Failed to send report."
