from __future__ import absolute_import, unicode_literals

import imaplib
import io
import subprocess
from datetime import datetime

from celery.utils.log import get_task_logger
from django.conf import settings

from arl.celery import app

from .helpers import upload_to_linode_object_storage, remove_old_backups

logger = get_task_logger(__name__)


@app.task(name="postgress_backup")
def create_db_backup_and_upload():
    database_name = settings.DATABASES["default"]["NAME"]
    database_user = settings.DATABASES["default"]["USER"]
    # backup_file = settings.BACKUP_FILE_PATH_DEV
    pg_dump_path = settings.BACKUP_DUMP_PATH
    current_date = datetime.now().strftime("%Y-%m-%d")
    # Run PostgreSQL pg_dump command and capture output in memory
    dump_command = f"{pg_dump_path} -U {database_user} -d {database_name}"
    try:
        # Run the command and capture the output
        backup_output = subprocess.check_output(dump_command, shell=True)

        # Create an in-memory buffer and write the output to it
        in_memory_backup = io.BytesIO(backup_output)

        # Reset the pointer to the beginning of the in-memory file
        in_memory_backup.seek(0)

        # Upload the in-memory backup file to Linode Object Storage
        object_key = f"POSTGRES/postgres_{current_date}.sql"
        upload_to_linode_object_storage(in_memory_backup, object_key)
        remove_old_backups()
        return f"Database backup created and uploaded successfully: {object_key}"

    except subprocess.CalledProcessError as e:
        print(f"An error occurred during backup or upload: {e}")
        return f"An error occurred during backup or upload: {e}"

    # Connect to the IMAP server
    mail = imaplib.IMAP4_SSL("outlook.office365.com", 993)

    # Login to the server
    mail.login("hr@1553690ontarioinc.com", "qivjed-Cakqys-7jyvwy")

    # Select a mailbox (inbox, for example)
    mail.select("inbox")

    # Search for unseen emails
    result, data = mail.search(None, "UNSEEN")

    # Process retrieved emails
    for num in data[0].split():
        result, data = mail.fetch(num, "(RFC822)")
        email_data = data[0][1]  # Raw email content

        # Process email content here
        # Example: Print email subject
        print(email_data)

    # Close the connection
    mail.close()
    mail.logout()
