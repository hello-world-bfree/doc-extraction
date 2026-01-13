import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


@dataclass
class S3Config:
    bucket_name: str
    prefix: str = "images/"
    region: str = "us-east-1"
    private: bool = True


class S3Uploader:
    def __init__(self, config: S3Config):
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is not installed. Install with: uv pip install -e '.[s3]'"
            )

        self.config = config
        self.s3_client = boto3.client('s3', region_name=config.region)

    def upload_image(
        self,
        local_path: Path,
        remote_key: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Optional[str]:
        if not local_path.exists():
            print(f"File not found: {local_path}")
            return None

        if remote_key is None:
            remote_key = f"{self.config.prefix}{local_path.name}"

        content_type, _ = mimetypes.guess_type(str(local_path))
        if not content_type:
            content_type = 'application/octet-stream'

        extra_args = {
            'ContentType': content_type,
        }

        if metadata:
            extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}

        if not self.config.private:
            extra_args['ACL'] = 'public-read'

        try:
            file_size = local_path.stat().st_size

            if file_size > 5 * 1024 * 1024:
                print(f"Uploading large file {local_path.name} using multipart upload")
                self.s3_client.upload_file(
                    str(local_path),
                    self.config.bucket_name,
                    remote_key,
                    ExtraArgs=extra_args
                )
            else:
                self.s3_client.upload_file(
                    str(local_path),
                    self.config.bucket_name,
                    remote_key,
                    ExtraArgs=extra_args
                )

            if self.config.private:
                s3_url = f"s3://{self.config.bucket_name}/{remote_key}"
            else:
                s3_url = f"https://{self.config.bucket_name}.s3.{self.config.region}.amazonaws.com/{remote_key}"

            return s3_url

        except NoCredentialsError:
            print("AWS credentials not found. Configure credentials using AWS CLI or IAM roles.")
            return None
        except ClientError as e:
            print(f"Failed to upload {local_path.name} to S3: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error uploading {local_path.name}: {e}")
            return None

    def upload_images(self, image_paths: list[Path], metadata_dict: Optional[dict] = None) -> dict[Path, str]:
        results = {}

        for image_path in image_paths:
            metadata = None
            if metadata_dict and image_path in metadata_dict:
                metadata = metadata_dict[image_path]

            s3_url = self.upload_image(image_path, metadata=metadata)
            if s3_url:
                results[image_path] = s3_url

        return results

    def download_image(self, remote_key: str, local_path: Path) -> bool:
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)

            self.s3_client.download_file(
                self.config.bucket_name,
                remote_key,
                str(local_path)
            )

            return True

        except ClientError as e:
            print(f"Failed to download {remote_key} from S3: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error downloading {remote_key}: {e}")
            return False

    def generate_presigned_url(self, remote_key: str, expiration: int = 3600) -> Optional[str]:
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.config.bucket_name,
                    'Key': remote_key
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"Failed to generate presigned URL for {remote_key}: {e}")
            return None
