
import boto3
from src.constants import REGION_NAME


class S3Client:

    s3_client = None
    s3_resource = None

    def __init__(self, region_name=REGION_NAME):
        """
        Creates AWS S3 client and resource.

        boto3 automatically looks for AWS credentials in the standard
        credential chain, including credentials configured using:

            aws configure

        Therefore, AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY do not
        need to be manually loaded using os.getenv().
        """

        if S3Client.s3_resource is None or S3Client.s3_client is None:

            # boto3 automatically finds credentials configured by
            # AWS CLI, environment variables, IAM roles, etc.
            S3Client.s3_resource = boto3.resource(
                "s3",
                region_name=region_name
            )

            S3Client.s3_client = boto3.client(
                "s3",
                region_name=region_name
            )

        self.s3_resource = S3Client.s3_resource
        self.s3_client = S3Client.s3_client
