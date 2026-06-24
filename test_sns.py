import os
import boto3
from dotenv import load_dotenv

load_dotenv()

sns_client = boto3.client(
    "sns",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

def test_sns(phone_number):
    e164 = "+919876543210"

    message = f"\U0001f6a8 HelpHive Emergency Alert Test"
    
    try:
        response = sns_client.publish(
            PhoneNumber=e164,
            Message=message,
            MessageAttributes={
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )
        print(f"[SNS] SUCCESS! SMS delivered to {e164} - MessageId: {response.get('MessageId')}")
    except Exception as e:
        print(f"[SNS] FAILED! SMS failed for {e164}: {type(e).__name__}: {e}")

test_sns("9876543210")
