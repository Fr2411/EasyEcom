'use client';

import type { FormEvent } from 'react';
import { useEffect, useRef, useState, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  getCatalogWorkspace,
  saveCatalogProduct,
} from '@/lib/api/commerce';
import {
  WorkspaceEmpty,
  WorkspaceHint,
  WorkspaceNotice,
  WorkspacePanel,
  WorkspaceToast,
} from '@/components/commerce/workspace-primitives';
import { ProductPhotoField } from '@/components/commerce/product-photo-field';
import type { CatalogProduct, ProductIdentityInput, ProductMedia } from '@/types/catalog';
import { formatQuantity, numberFromString } from '@/lib/commerce-format';
import styles from '@/components/commerce/catalog-library-workspace.module.css';

const EMPTY_IDENTITY: ProductIdentityInput = {
  product_name: '',
  supplier: '',
  category: '',
  brand: '',
  description: '',
  image_url: '',
  pending_primary_media_upload_id: '',
  remove_primary_image: false,
  sku_root: '',
  default_selling_price: '',
  min_selling_price: '',
  max_discount_percent: '',
  status: 'active',
};

type CatalogIdentityDraft = {
  product_id?: string;
  identity: ProductIdentityInput;
};

function valueOrEmpty(value: string | null | undefined) {
  return value ?? '';
}

function identityFromProduct(product: CatalogProduct): ProductIdentityInput {
  return {
    ...EMPTY_IDENTITY,
    product_name: product.name,
    supplier: product.supplier,
    category: product.category,
    brand: product.brand,
    description: product.description,
    image_url: product.image_url,
    sku_root: product.sku_root,
    default_selling_price: valueOrEmpty(product.default_price),
    min_selling_price: valueOrEmpty(product.min_price),
    max_discount_percent: valueOrEmpty(product.max_discount_percent),
    status: product.status || 'active',
  };
}

function normalizeIdentity(identity: ProductIdentityInput): ProductIdentityInput {
  return {
    ...identity,
    product_name: identity.product_name.trim(),
    supplier: identity.supplier.trim(),
    category: identity.category.trim(),
    brand: identity.brand.trim(),
    description: identity.description.trim(),
    image_url: identity.image_url.trim(),
    pending_primary_media_upload_id: (identity.pending_primary_media_upload_id || '').trim(),
    sku_root: identity.sku_root.trim(),
    default_selling_price: identity.default_selling_price.trim(),
    min_selling_price: identity.min_selling_price.trim(),
    max_discount_percent: (identity.max_discount_percent || '').trim(),
    status: (identity.status || 'active').trim() || 'active',
    remove_primary_image: Boolean(identity.remove_primary_image),
  };
}

function availableStockTotal(product: CatalogProduct) {
  return product.variants.reduce((sum, variant) => sum + numberFromString(variant.available_to_sell), 0);
}

export function CatalogLibraryWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();

  const [queryInput, setQueryInput] = useState('');
  const [workspace, setWorkspace] = useState<Awaited<ReturnType<typeof getCatalogWorkspace>> | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [draft, setDraft] = useState<CatalogIdentityDraft>({ identity: { ...EMPTY_IDENTITY } });
  const [productImage, setProductImage] = useState<ProductMedia | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [savePending, setSavePending] = useState(false);
  const [isPending, startTransition] = useTransition();

  const openedFromParamRef = useRef('');

  useEffect(() => {
    if (!toast) return undefined;
    const timeoutId = window.setTimeout(() => setToast(''), 2800);
    return () => window.clearTimeout(timeoutId);
  }, [toast]);

  const loadWorkspace = (query = '') => {
    const trimmed = query.trim();
    startTransition(async () => {
      try {
        const payload = await getCatalogWorkspace({ q: trimmed });
        setWorkspace(payload);
        setError('');
      } catch (loadError) {
        setWorkspace(null);
        setError(loadError instanceof Error ? loadError.message : 'Unable to load catalog right now.');
      }
    });
  };

  useEffect(() => {
    const query = (searchParams.get('q') || '').trim();
    setQueryInput(query);
    loadWorkspace(query);
  }, [searchKey]);

  useEffect(() => {
    if (!workspace) return;
    const requestedProductId = (searchParams.get('product_id') || '').trim();
    if (!requestedProductId) {
      openedFromParamRef.current = '';
      return;
    }
    if (openedFromParamRef.current === requestedProductId) {
      return;
    }
    const product = workspace.items.find((item) => item.product_id === requestedProductId);
    if (!product) return;
    openedFromParamRef.current = requestedProductId;
    setDraft({
      product_id: product.product_id,
      identity: identityFromProduct(product),
    });
    setProductImage(product.image);
    setDrawerOpen(true);
  }, [workspace, searchKey]);

  const openNewProduct = () => {
    setDraft({
      identity: {
        ...EMPTY_IDENTITY,
        product_name: queryInput.trim(),
      },
    });
    setProductImage(null);
    setNotice('');
    setError('');
    setDrawerOpen(true);
  };

  const openEditProduct = (product: CatalogProduct) => {
    setDraft({
      product_id: product.product_id,
      identity: identityFromProduct(product),
    });
    setProductImage(product.image);
    setNotice('');
    setError('');
    setDrawerOpen(true);
  };

  const saveProductIdentity = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSavePending(true);
    setError('');
    setNotice('');
    try {
      const identity = normalizeIdentity(draft.identity);
      if (identity.product_name.length < 2) {
        setError('Product name must be at least 2 characters.');
        return;
      }
      const response = await saveCatalogProduct({
        product_id: draft.product_id,
        identity,
        variants: [],
      });
      setNotice(`Saved product: ${response.product.name}.`);
      setToast('Catalog product saved.');
      setDrawerOpen(false);
      loadWorkspace(queryInput);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save product identity.');
    } finally {
      setSavePending(false);
    }
  };

  return (
    <div className="workspace-stack">
      {toast ? <WorkspaceToast message={toast} onClose={() => setToast('')} /> : null}

      <WorkspacePanel
        title={
          <span className="workspace-heading">
            Catalog
            <WorkspaceHint
              label="Catalog help"
              text="Catalog is your product library. Add or edit product identity here. Stock operations happen in Inventory."
            />
          </span>
        }
        description="View products as cards, edit identity fields, and keep catalog data separate from stock operations."
        actions={
          <div className={styles.toolbar}>
            <form
              className={styles.searchForm}
              onSubmit={(event) => {
                event.preventDefault();
                loadWorkspace(queryInput);
              }}
            >
              <input
                id="catalog-search-input"
                type="search"
                value={queryInput}
                placeholder="Search products"
                onChange={(event) => setQueryInput(event.target.value)}
              />
              <button type="submit" disabled={isPending}>Search</button>
            </form>
            <button type="button" onClick={openNewProduct}>
              Add New Product
            </button>
          </div>
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !workspace ? <WorkspaceNotice>Loading catalog…</WorkspaceNotice> : null}

        {workspace?.items.length ? (
          <div className={styles.grid}>
            {workspace.items.map((product) => (
              <button
                key={product.product_id}
                type="button"
                className={styles.cardButton}
                onClick={() => openEditProduct(product)}
              >
                <div className={styles.cardImageWrap}>
                  {product.image?.thumbnail_url ? (
                    <img src={product.image.thumbnail_url} alt={product.name} />
                  ) : (
                    <span className={styles.cardImagePlaceholder}>{product.name.charAt(0).toUpperCase()}</span>
                  )}
                </div>
                <div className={styles.cardBody}>
                  <div className={styles.cardTitleRow}>
                    <strong>{product.name}</strong>
                    <span className="workspace-field-note">{product.status}</span>
                  </div>
                  <p className={styles.cardMeta}>
                    {product.brand || 'No brand'} · {product.category || 'No category'} · {product.supplier || 'No supplier'}
                  </p>
                  <p className={styles.cardMeta}>
                    Available variants: {product.variants.length} · Available stock: {formatQuantity(availableStockTotal(product))}
                  </p>
                  {product.variants.length ? (
                    <div className={styles.variantList}>
                      {product.variants.slice(0, 4).map((variant) => (
                        <span key={variant.variant_id} className={styles.variantChip}>
                          {variant.title} ({formatQuantity(variant.available_to_sell)})
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="workspace-field-note">No in-stock variants currently.</p>
                  )}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <WorkspaceEmpty
            title="No products found"
            message="Add a product from the top-right button, or clear the search query."
          />
        )}
      </WorkspacePanel>

      {drawerOpen ? (
        <>
          <button
            type="button"
            className={styles.drawerBackdrop}
            aria-label="Close product drawer"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className={styles.drawer} aria-label="Catalog product editor">
            <div className={styles.drawerHeader}>
              <h3 className="workspace-heading">
                {draft.product_id ? 'Edit Product' : 'Add New Product'}
              </h3>
              <button type="button" className="secondary" onClick={() => setDrawerOpen(false)}>
                Close
              </button>
            </div>

            <form className="workspace-form" onSubmit={saveProductIdentity}>
              <div className="workspace-form-grid">
                <label>
                  Product name
                  <input
                    value={draft.identity.product_name}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        identity: { ...current.identity, product_name: event.target.value },
                      }))
                    }
                    required
                  />
                </label>
                <label>
                  Supplier
                  <input
                    value={draft.identity.supplier}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        identity: { ...current.identity, supplier: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Category
                  <input
                    value={draft.identity.category}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        identity: { ...current.identity, category: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Brand
                  <input
                    value={draft.identity.brand}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        identity: { ...current.identity, brand: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  SKU Base
                  <input
                    value={draft.identity.sku_root}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        identity: { ...current.identity, sku_root: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Default selling price
                  <input
                    value={draft.identity.default_selling_price}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        identity: { ...current.identity, default_selling_price: event.target.value },
                      }))
                    }
                    inputMode="decimal"
                  />
                </label>
                <label>
                  Minimum selling price
                  <input
                    value={draft.identity.min_selling_price}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        identity: { ...current.identity, min_selling_price: event.target.value },
                      }))
                    }
                    inputMode="decimal"
                  />
                </label>
                <div className="field-span-2">
                  <label>Product photo</label>
                  <ProductPhotoField
                    image={productImage}
                    onUploaded={(image) => {
                      setProductImage(image);
                      setDraft((current) => ({
                        ...current,
                        identity: {
                          ...current.identity,
                          pending_primary_media_upload_id: image.upload_id,
                          remove_primary_image: false,
                          image_url: image.large_url,
                        },
                      }));
                    }}
                    onRemove={() => {
                      setProductImage(null);
                      setDraft((current) => ({
                        ...current,
                        identity: {
                          ...current.identity,
                          pending_primary_media_upload_id: '',
                          remove_primary_image: Boolean(current.product_id || current.identity.image_url),
                          image_url: '',
                        },
                      }));
                    }}
                  />
                </div>
              </div>

              <label>
                Description
                <textarea
                  rows={3}
                  value={draft.identity.description}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      identity: { ...current.identity, description: event.target.value },
                    }))
                  }
                />
              </label>

              <div className={styles.drawerActions}>
                <button type="submit" disabled={savePending}>
                  {savePending ? 'Saving…' : 'Save Product'}
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    const productName = draft.identity.product_name.trim();
                    router.push(productName ? `/inventory?q=${encodeURIComponent(productName)}` : '/inventory');
                  }}
                >
                  Open Inventory
                </button>
              </div>
            </form>
          </aside>
        </>
      ) : null}
    </div>
  );
}
