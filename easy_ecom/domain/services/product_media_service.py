from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, BinaryIO

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import ProductMediaModel, ProductModel, ProductVectorModel


IMAGE_CANVAS_SIZE = 768
LARGE_MAX_EDGE = 2048
THUMB_CANVAS_SIZE = 256
IMAGE_QUALITY = 82
THUMB_QUALITY = 68
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class RenderedMedia:
    large_bytes: bytes
    thumbnail_bytes: bytes
    checksum_sha256: str
    large_width: int
    large_height: int
    thumbnail_width: int
    thumbnail_height: int


class ProductMediaService:
    def __init__(self) -> None:
        self._bucket = settings.product_media_s3_bucket.strip()
        self._prefix = settings.product_media_s3_prefix.strip("/") or "clients"
        self._region = settings.aws_region
        self._client: Any = None

    def _require_bucket(self) -> None:
        if not self._bucket:
            raise ApiException(
                status_code=503,
                code="PRODUCT_MEDIA_NOT_CONFIGURED",
                message="Product media storage is not configured.",
            )

    def _s3(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:
                raise ApiException(
                    status_code=503,
                    code="PRODUCT_MEDIA_RUNTIME_MISSING",
                    message="Product media dependencies are not installed.",
                ) from exc
            self._client = boto3.client("s3", region_name=self._region)
        return self._client

    def _key(self, *parts: str) -> str:
        return "/".join([self._prefix, *[part.strip("/") for part in parts if part]])

    def _staged_key(self, client_id: str, upload_id: str, filename: str) -> str:
        return self._key(client_id, "product-media", "staged", upload_id, filename)

    def _product_key(self, client_id: str, product_id: str, media_id: str, filename: str) -> str:
        return self._key(client_id, "products", product_id, "primary", media_id, filename)

    def _upload_bytes(self, key: str, payload: bytes, content_type: str) -> None:
        self._require_bucket()
        self._s3().put_object(
            Bucket=self._bucket,
            Key=key,
            Body=payload,
            ContentType=content_type,
        )

    def _move_object(self, source_key: str, target_key: str, content_type: str) -> None:
        self._require_bucket()
        s3 = self._s3()
        if source_key == target_key:
            return
        s3.copy_object(
            Bucket=self._bucket,
            CopySource={"Bucket": self._bucket, "Key": source_key},
            Key=target_key,
            ContentType=content_type,
            MetadataDirective="REPLACE",
        )
        s3.delete_object(Bucket=self._bucket, Key=source_key)

    def delete_object(self, key: str) -> None:
        if not key:
            return
        self._require_bucket()
        self._s3().delete_object(Bucket=self._bucket, Key=key)

    def signed_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        if not key:
            return ""
        self._require_bucket()
        return self._s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )

    def _normalize_image(self, source: bytes) -> RenderedMedia:
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
        except ImportError as exc:
            raise ApiException(
                status_code=503,
                code="PRODUCT_MEDIA_RUNTIME_MISSING",
                message="Product media dependencies are not installed.",
            ) from exc
        try:
            image = Image.open(io.BytesIO(source))
        except UnidentifiedImageError as exc:
            raise ApiException(status_code=400, code="INVALID_IMAGE", message="Unsupported image file.") from exc

        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        checksum = hashlib.sha256(source).hexdigest()

        def render_large(fmt: str, quality: int) -> tuple[bytes, int, int]:
            working = image.copy()
            working.thumbnail((LARGE_MAX_EDGE, LARGE_MAX_EDGE), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            save_kwargs = {"quality": quality, "optimize": True}
            if fmt == "JPEG":
                save_kwargs["progressive"] = True
            working.save(output, format=fmt, **save_kwargs)
            return output.getvalue(), working.width, working.height

        def render_square(canvas_size: int, fmt: str, quality: int) -> tuple[bytes, int, int]:
            working = image.copy()
            working.thumbnail((canvas_size, canvas_size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (canvas_size, canvas_size), (255, 255, 255))
            offset = ((canvas_size - working.width) // 2, (canvas_size - working.height) // 2)
            canvas.paste(working, offset)
            output = io.BytesIO()
            save_kwargs = {"quality": quality, "optimize": True}
            if fmt == "JPEG":
                save_kwargs["progressive"] = True
            canvas.save(output, format=fmt, **save_kwargs)
            return output.getvalue(), canvas.width, canvas.height

        large_bytes, large_width, large_height = render_large("JPEG", IMAGE_QUALITY)
        thumbnail_bytes, thumbnail_width, thumbnail_height = render_square(THUMB_CANVAS_SIZE, "WEBP", THUMB_QUALITY)

        return RenderedMedia(
            large_bytes=large_bytes,
            thumbnail_bytes=thumbnail_bytes,
            checksum_sha256=checksum,
            large_width=large_width,
            large_height=large_height,
            thumbnail_width=thumbnail_width,
            thumbnail_height=thumbnail_height,
        )

    def _read_upload_bytes(self, upload_file: BinaryIO) -> bytes:
        payload = upload_file.read()
        if not payload:
            raise ApiException(status_code=400, code="EMPTY_IMAGE", message="Image upload is empty.")
        if len(payload) > MAX_UPLOAD_BYTES:
            raise ApiException(status_code=413, code="IMAGE_TOO_LARGE", message="Image upload is too large.")
        return payload

    def create_staged_upload(self, session: Session, *, client_id: str, user_id: str, upload_file) -> dict[str, object]:
        source = self._read_upload_bytes(upload_file.file)
        rendered = self._normalize_image(source)
        media_id = new_uuid()
        large_key = self._staged_key(client_id, media_id, "image-768.jpg")
        thumb_key = self._staged_key(client_id, media_id, "thumb-256.webp")
        self._upload_bytes(large_key, rendered.large_bytes, "image/jpeg")
        self._upload_bytes(thumb_key, rendered.thumbnail_bytes, "image/webp")

        media = ProductMediaModel(
            product_media_id=media_id,
            client_id=client_id,
            product_id=None,
            status="staged",
            role="primary",
            large_object_key=large_key,
            thumbnail_object_key=thumb_key,
            large_mime_type="image/jpeg",
            thumbnail_mime_type="image/webp",
            large_width=rendered.large_width,
            large_height=rendered.large_height,
            thumbnail_width=rendered.thumbnail_width,
            thumbnail_height=rendered.thumbnail_height,
            checksum_sha256=rendered.checksum_sha256,
            uploaded_by_user_id=user_id,
        )
        session.add(media)
        session.flush()
        return self.media_payload(media, vector_status="pending")

    def media_payload(self, media: ProductMediaModel | None, *, vector_status: str = "pending") -> dict[str, object] | None:
        if media is None:
            return None
        return {
            "media_id": str(media.product_media_id),
            "upload_id": str(media.product_media_id),
            "large_url": self.signed_url(media.large_object_key),
            "thumbnail_url": self.signed_url(media.thumbnail_object_key),
            "width": int(media.large_width),
            "height": int(media.large_height),
            "vector_status": vector_status,
        }

    def media_payload_map(self, session: Session, *, client_id: str, media_ids: set[str]) -> dict[str, dict[str, object]]:
        if not media_ids:
            return {}
        media_rows = session.execute(
            select(ProductMediaModel).where(
                ProductMediaModel.client_id == client_id,
                ProductMediaModel.product_media_id.in_(media_ids),
            )
        ).scalars().all()
        vector_rows = session.execute(
            select(ProductVectorModel).where(
                ProductVectorModel.client_id == client_id,
                ProductVectorModel.product_media_id.in_(media_ids),
            )
        ).scalars().all()
        vector_status_by_media = {
            str(vector.product_media_id): vector.status
            for vector in vector_rows
        }
        return {
            str(media.product_media_id): self.media_payload(
                media,
                vector_status=vector_status_by_media.get(str(media.product_media_id), "pending"),
            )
            for media in media_rows
        }

    def attach_staged_upload(
        self,
        session: Session,
        *,
        client_id: str,
        product_id: str,
        staged_upload_id: str,
        user_id: str | None,
    ) -> ProductMediaModel:
        media = session.execute(
            select(ProductMediaModel).where(
                ProductMediaModel.client_id == client_id,
                ProductMediaModel.product_media_id == staged_upload_id,
            )
        ).scalar_one_or_none()
        if media is None:
            raise ApiException(status_code=404, code="PRODUCT_MEDIA_NOT_FOUND", message="Uploaded product image was not found.")
        if media.status not in {"staged", "attached"}:
            raise ApiException(status_code=409, code="PRODUCT_MEDIA_UNAVAILABLE", message="Uploaded product image is not available.")

        product = session.execute(
            select(ProductModel).where(
                ProductModel.client_id == client_id,
                ProductModel.product_id == product_id,
            )
        ).scalar_one_or_none()
        if product is None:
            raise ApiException(status_code=404, code="PRODUCT_NOT_FOUND", message="Product was not found.")

        previous_primary = None
        if product.primary_media_id:
            previous_primary = session.execute(
                select(ProductMediaModel).where(
                    ProductMediaModel.client_id == client_id,
                    ProductMediaModel.product_media_id == product.primary_media_id,
                )
            ).scalar_one_or_none()
            if previous_primary and str(previous_primary.product_media_id) != str(media.product_media_id):
                previous_primary.status = "archived"

        target_large_key = self._product_key(client_id, product_id, str(media.product_media_id), "image-768.jpg")
        target_thumb_key = self._product_key(client_id, product_id, str(media.product_media_id), "thumb-256.webp")
        if media.status == "staged":
            self._move_object(media.large_object_key, target_large_key, media.large_mime_type)
            self._move_object(media.thumbnail_object_key, target_thumb_key, media.thumbnail_mime_type)

        media.large_object_key = target_large_key
        media.thumbnail_object_key = target_thumb_key
        media.product_id = product_id
        media.status = "attached"
        media.role = "primary"
        media.uploaded_by_user_id = user_id
        media.attached_at = now_utc()
        product.primary_media_id = str(media.product_media_id)
        product.image_url = media.large_object_key

        vector = session.execute(
            select(ProductVectorModel).where(
                ProductVectorModel.client_id == client_id,
                ProductVectorModel.product_id == product_id,
                ProductVectorModel.product_media_id == media.product_media_id,
            )
        ).scalar_one_or_none()
        if vector is None:
            session.add(
                ProductVectorModel(
                    product_vector_id=new_uuid(),
                    client_id=client_id,
                    product_id=product_id,
                    product_media_id=str(media.product_media_id),
                    status="pending",
                    provider="",
                    embedding_ref="",
                    source_object_key=media.large_object_key,
                )
            )
        else:
            vector.status = vector.status or "pending"
            vector.source_object_key = media.large_object_key
        session.flush()
        return media

    def remove_primary_media(self, session: Session, *, client_id: str, product_id: str) -> None:
        product = session.execute(
            select(ProductModel).where(
                ProductModel.client_id == client_id,
                ProductModel.product_id == product_id,
            )
        ).scalar_one_or_none()
        if product is None:
            raise ApiException(status_code=404, code="PRODUCT_NOT_FOUND", message="Product was not found.")
        if product.primary_media_id:
            media = session.execute(
                select(ProductMediaModel).where(
                    ProductMediaModel.client_id == client_id,
                    ProductMediaModel.product_media_id == product.primary_media_id,
                )
            ).scalar_one_or_none()
            if media is not None:
                media.status = "archived"
        product.primary_media_id = None
        product.image_url = ""
        session.flush()

    def cleanup_expired_staged_uploads(self, session: Session) -> int:
        cutoff = now_utc() - timedelta(hours=settings.product_media_staged_ttl_hours)
        staged = session.execute(
            select(ProductMediaModel).where(
                ProductMediaModel.status == "staged",
                ProductMediaModel.created_at < cutoff,
            )
        ).scalars().all()
        count = 0
        for media in staged:
            self.delete_object(media.large_object_key)
            self.delete_object(media.thumbnail_object_key)
            session.execute(
                delete(ProductVectorModel).where(ProductVectorModel.product_media_id == media.product_media_id)
            )
            session.delete(media)
            count += 1
        session.flush()
        return count
