import os
import uuid
from django.conf import settings
from rest_framework.views import APIView
from core.views.system import success_response
from django.core.exceptions import ValidationError
from minio import Minio
from users.permissions import HasPermission

class FileUploadView(APIView):
    def post(self, request):
        if not HasPermission('tenant:update')().has_permission(request, self):
            self.permission_denied(request)

        file_obj = request.FILES.get('file')
        if not file_obj:
            raise ValidationError("No file provided")

        ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
        ALLOWED_MIME_TYPES = {'image/png', 'image/jpeg', 'image/pjpeg', 'image/webp', 'image/svg+xml'}
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

        extension = os.path.splitext(file_obj.name)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise ValidationError(f"Định dạng tệp '{extension}' không được phép. Chỉ chấp nhận các định dạng ảnh: .png, .jpg, .jpeg, .webp, .svg")

        content_type = getattr(file_obj, 'content_type', '').lower()
        if content_type and content_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(f"Loại nội dung '{content_type}' không hợp lệ cho hình ảnh logo.")

        if file_obj.size > MAX_FILE_SIZE:
            raise ValidationError("Kích thước tệp vượt quá giới hạn tối đa cho phép (5MB).")

        try:
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            
            bucket_name = settings.MINIO_BUCKET_NAME
            
            # Check if bucket exists, if not, create it
            found = client.bucket_exists(bucket_name)
            if not found:
                client.make_bucket(bucket_name)
                
            # Always ensure the bucket has a public read policy so logos can be displayed
            import json
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                    }
                ]
            }
            client.set_bucket_policy(bucket_name, json.dumps(policy))

            extension = os.path.splitext(file_obj.name)[1]
            object_name = f"logos/{uuid.uuid4()}{extension}"
            
            client.put_object(
                bucket_name,
                object_name,
                file_obj.file,
                length=file_obj.size,
                content_type=file_obj.content_type
            )
            
            url = f"{settings.MINIO_PUBLIC_URL}/{bucket_name}/{object_name}"
            
            return success_response({"url": url})
            
        except Exception as e:
            raise ValidationError(f"Error occurred: {str(e)}")
