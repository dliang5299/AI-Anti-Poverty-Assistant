# Initialize
# import boto3
import sagemaker
from sagemaker import get_execution_role
from sagemaker.jumpstart.model import JumpStartModel

# Create SageMaker session
sagemaker_session = sagemaker.Session()

# Get the execution role (works only in SageMaker notebook/lab environment)
role = get_execution_role()

# S3 bucket and prefix
bucket = sagemaker_session.default_bucket()
prefix = "AI-Anti-Poverty-Assistant/data"

# sm = boto3.client("sagemaker")

# Create JS endpoint
js_model = JumpStartModel(model_id="meta-textgeneration-llama-3-1-70b-instruct", role=sagemaker_session.get_caller_identity_arn())
predictor = js_model.deploy(instance_type="ml.g5.2xlarge", initial_instance_count=1)
JUMPSTART_ENDPOINT = predictor.endpoint_name

