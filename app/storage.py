import os
import uuid
import datetime
import io
from minio import Minio
from minio.error import S3Error

# internal upload client (no TLS, ClusterIP)
UPLOAD_CLIENT = Minio(
    "docgen-minio.docgen-storage.svc.cluster.local:9000",
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)

# external presign‐only client (public hostname, TLS)
PUBLIC_HOST = "miniofiles.lesso.co.uk"
PRESIGN_CLIENT = Minio(
    PUBLIC_HOST,
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=True,
)

BUCKET = os.environ.get("MINIO_BUCKET", "lesso-docgen")

# ensure bucket exists on startup
try:
    if not UPLOAD_CLIENT.bucket_exists(BUCKET):
        UPLOAD_CLIENT.make_bucket(BUCKET)
except S3Error as e:
    # might race if already created—just log
    print(f"[storage] bucket check/create failed: {e}")

def upload_and_presign(
    tenant: str,
    ext: str,
    payload: bytes,
    expires: int = 24 * 3600,  # seconds
) -> str:
    """Upload bytes → MinIO, return presigned URL."""
    today = datetime.datetime.utcnow()
    obj_name = f"{tenant}/{today:%Y/%m}/{uuid.uuid4()}.{ext}"

    # upload to internal endpoint
    UPLOAD_CLIENT.put_object(
        BUCKET,
        obj_name,
        data=io.BytesIO(payload),
        length=len(payload),
        content_type=f"application/{ext}",
    )

    # wrap expires in a timedelta
    expiry_delta = datetime.timedelta(seconds=expires)

    # generate a presigned URL via public endpoint
    return PRESIGN_CLIENT.presigned_get_object(
        BUCKET,
        obj_name,
        expires=expiry_delta,
    )

