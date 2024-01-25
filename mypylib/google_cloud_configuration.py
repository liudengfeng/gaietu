import json

# import vertexai
from google.cloud import aiplatform
from google.oauth2.service_account import Credentials
from vertexai.preview.generative_models import HarmBlockThreshold, HarmCategory

PROJECT_ID = "gllm-409401"
LOCATION = "asia-northeast1"

# 屏蔽大部分
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
]

# BLOCK_LOW_AND_ABOVE 会触发大部分的屏蔽
HARM_BLOCK_CONFIG = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
}

# DEFAULT_SAFETY_SETTINGS = {
#     HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
#     HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
#     HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
#     HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
# }

DEFAULT_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}


def get_google_service_account_info(secrets):
    # 由于private_key含有大量的换行符号，所以单独存储
    service_account_info = json.loads(secrets["Google"]["GOOGLE_CREDENTIALS"])
    service_account_info["private_key"] = secrets["Google"]["GOOGLE_PRIVATE_KEY"]
    return service_account_info


def get_google_credentials(secrets):
    service_account_info = get_google_service_account_info(secrets)
    # 创建凭据
    return Credentials.from_service_account_info(service_account_info)


def google_configure(secrets):
    # 创建凭据
    credentials = get_google_credentials(secrets)
    aiplatform.init(
        # your Google Cloud Project ID or number
        # environment default used is not set
        # project=PROJECT_ID,
        # the Vertex AI region you will use
        # defaults to us-central1
        # location=LOCATION,
        # Google Cloud Storage bucket in same region as location
        # used to stage artifacts
        # staging_bucket="gs://my_staging_bucket",
        # custom google.auth.credentials.Credentials
        # environment default credentials used if not set
        credentials=credentials,
        # customer managed encryption key resource name
        # will be applied to all Vertex AI resources if set
        # encryption_spec_key_name=my_encryption_key_name,
        # the name of the experiment to use to track
        # logged metrics and parameters
        # experiment="gllm-experiment",
        # description of the experiment above
        # experiment_description="云端使用vertex ai",
    )
    # vertexai.init(project=PROJECT_ID, location=LOCATION)
