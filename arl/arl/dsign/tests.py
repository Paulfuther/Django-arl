from unittest.mock import patch
from django.test import TestCase
from arl.dsign.models import CustomUser
from arl.dsign.tasks import process_docusign_webhook  # Ensure correct import paths


class DocuSignWebhookTests(TestCase):
    def setUp(self):
        # Initialize data for a New Hire scenario
        self.payload_new_hire = {
            "event": "recipient-completed",
            "data": {
                "envelopeId": "12345",
                "envelopeSummary": {
                    "recipients": {
                        "signers": [
                            {
                                "email": "newhire@example.com",
                                "phone_number": "+15196707469",
                            }
                        ]
                    }
                },
            },
        }
        # Create a user in the test database
        self.user = CustomUser.objects.create(
            email="newhire@example.com", username="newhire", phone_number="+15196707469"
        )

    @patch("arl.dsign.tasks.get_template_id")
    @patch("arl.dsign.tasks.get_docusign_template_name_from_template")
    def test_new_hire_process(self, mock_get_template_name, mock_get_template_id):
        # Mock external dependencies within the task
        mock_get_template_id.return_value = "c30a27b4-fd10-4fdd-b6e3-78ddd3e06463"
        mock_get_template_name.return_value = "New Hire File"

        # Call the webhook processing function with the new hire payload
        result = process_docusign_webhook(self.payload_new_hire)

        # Check if the processing result indicates success or specific behavior
        self.assertTrue(
            result, "Webhook processing should return success for new hires"
        )

    @patch("arl.dsign.tasks.get_template_id")
    @patch("arl.dsign.tasks.get_docusign_template_name_from_template")
    def test_standard_release_process_ignored(
        self, mock_get_template_name, mock_get_template_id
    ):
        # Setup the mock to return values that signify a Standard Release document
        mock_get_template_id.return_value = "template_id_for_standard_release"
        mock_get_template_name.return_value = "Standard Release"

        # Modify the payload as it might be for a Standard Release
        self.payload_new_hire["data"]["envelopeSummary"]["recipients"]["signers"][0] = {
            "email": "standard@example.com",
            "phone_number": "+15196707469",
        }
        self.payload_new_hire["data"]["event"] = "recipient-completed"

        # Call the webhook processing function with the modified payload
        result = process_docusign_webhook(self.payload_new_hire)

        # Expecting the function to return None or similar to indicate no significant action
        self.assertIsNone(
            result, "Function should effectively do nothing for Standard Release forms"
        )
