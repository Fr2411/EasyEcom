BEGIN;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS primary_media_id UUID;

CREATE TABLE IF NOT EXISTS product_media (
    product_media_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(product_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'staged',
    role VARCHAR(32) NOT NULL DEFAULT 'primary',
    large_object_key VARCHAR(512) NOT NULL,
    thumbnail_object_key VARCHAR(512) NOT NULL,
    large_mime_type VARCHAR(64) NOT NULL DEFAULT 'image/jpeg',
    thumbnail_mime_type VARCHAR(64) NOT NULL DEFAULT 'image/webp',
    large_width INTEGER NOT NULL DEFAULT 768,
    large_height INTEGER NOT NULL DEFAULT 768,
    thumbnail_width INTEGER NOT NULL DEFAULT 256,
    thumbnail_height INTEGER NOT NULL DEFAULT 256,
    checksum_sha256 VARCHAR(128) NOT NULL DEFAULT '',
    uploaded_by_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    attached_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_products_primary_media_id
    ON products(primary_media_id);

CREATE INDEX IF NOT EXISTS ix_product_media_client_id
    ON product_media(client_id);

CREATE INDEX IF NOT EXISTS ix_product_media_product_id
    ON product_media(product_id);

CREATE INDEX IF NOT EXISTS ix_product_media_status
    ON product_media(status);

CREATE INDEX IF NOT EXISTS ix_product_media_role
    ON product_media(role);

CREATE INDEX IF NOT EXISTS ix_product_media_client_product_status
    ON product_media(client_id, product_id, status);

CREATE TABLE IF NOT EXISTS product_vectors (
    product_vector_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    product_media_id UUID NOT NULL REFERENCES product_media(product_media_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    provider VARCHAR(64) NOT NULL DEFAULT '',
    embedding_ref VARCHAR(255) NOT NULL DEFAULT '',
    source_object_key VARCHAR(512) NOT NULL DEFAULT '',
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_product_vectors_client_product_media UNIQUE (client_id, product_id, product_media_id)
);

CREATE INDEX IF NOT EXISTS ix_product_vectors_client_id
    ON product_vectors(client_id);

CREATE INDEX IF NOT EXISTS ix_product_vectors_product_id
    ON product_vectors(product_id);

CREATE INDEX IF NOT EXISTS ix_product_vectors_product_media_id
    ON product_vectors(product_media_id);

CREATE INDEX IF NOT EXISTS ix_product_vectors_status
    ON product_vectors(status);

COMMIT;
