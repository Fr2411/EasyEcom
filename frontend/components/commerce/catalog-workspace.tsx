'use client';

import { FormEvent, useEffect, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import { getCatalogWorkspace, saveCatalogProduct } from '@/lib/api/commerce';
import type {
  CatalogProduct,
  CatalogUpsertPayload,
  CatalogVariantInput,
  ProductIdentityInput,
  VariantOptions,
} from '@/types/catalog';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel, WorkspaceTabs } from '@/components/commerce/workspace-primitives';
import { formatMoney, formatQuantity } from '@/lib/commerce-format';


type CatalogTab = 'products' | 'edit';

const EMPTY_IDENTITY: ProductIdentityInput = {
  product_name: '',
  supplier: '',
  category: '',
  brand: '',
  description: '',
  image_url: '',
  sku_root: '',
  default_selling_price: '0',
  min_selling_price: '0',
  max_discount_percent: '0',
  status: 'active',
};

const EMPTY_VARIANT: CatalogVariantInput = {
  sku: '',
  barcode: '',
  size: '',
  color: '',
  other: '',
  default_purchase_price: '0',
  default_selling_price: '0',
  min_selling_price: '0',
  reorder_level: '0',
  status: 'active',
};


function variantToInput(options: VariantOptions, variant: CatalogProduct['variants'][number]): CatalogVariantInput {
  return {
    variant_id: variant.variant_id,
    sku: variant.sku,
    barcode: variant.barcode,
    size: options.size,
    color: options.color,
    other: options.other,
    default_purchase_price: variant.unit_cost,
    default_selling_price: variant.unit_price,
    min_selling_price: variant.min_price,
    reorder_level: variant.reorder_level,
    status: variant.status,
  };
}


function productToPayload(product: CatalogProduct): CatalogUpsertPayload {
  return {
    product_id: product.product_id,
    identity: {
      product_name: product.name,
      supplier: product.supplier,
      category: product.category,
      brand: product.brand,
      description: product.description,
      image_url: '',
      sku_root: product.sku_root,
      default_selling_price: product.default_price,
      min_selling_price: product.min_price,
      max_discount_percent: product.max_discount_percent,
      status: product.status,
    },
    variants: product.variants.map((variant) => variantToInput(variant.options, variant)),
  };
}


export function CatalogWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [activeTab, setActiveTab] = useState<CatalogTab>('products');
  const [queryInput, setQueryInput] = useState('');
  const [workspace, setWorkspace] = useState<Awaited<ReturnType<typeof getCatalogWorkspace>> | null>(null);
  const [form, setForm] = useState<CatalogUpsertPayload>({
    identity: EMPTY_IDENTITY,
    variants: [{ ...EMPTY_VARIANT }],
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isPending, startTransition] = useTransition();

  const loadWorkspace = (query = '') => {
    startTransition(async () => {
      try {
        const payload = await getCatalogWorkspace({ q: query });
        setWorkspace(payload);
        setError('');
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load catalog workspace.');
      }
    });
  };

  useEffect(() => {
    const query = searchParams.get('q') ?? '';
    setQueryInput(query);
    loadWorkspace(query);
  }, [searchKey]);

  const onSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loadWorkspace(queryInput.trim());
  };

  const onProductEdit = (product: CatalogProduct) => {
    setForm(productToPayload(product));
    setActiveTab('edit');
    setNotice('');
  };

  const onSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice('');
    setError('');
    try {
      const payload = {
        ...form,
        variants: form.variants.filter((variant) => variant.sku.trim()),
      };
      const response = await saveCatalogProduct(payload);
      setForm(productToPayload(response.product));
      setNotice(payload.product_id ? 'Product updated.' : 'Product created.');
      setActiveTab('products');
      await loadWorkspace(queryInput.trim());
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save product.');
    }
  };

  return (
    <div className="workspace-stack">
      <WorkspaceTabs
        tabs={[
          { id: 'products', label: 'Products' },
          { id: 'edit', label: form.product_id ? 'Edit Product' : 'Add Product' },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <WorkspacePanel
        title="Variant-first catalog"
        description="Search and manage products as parent records with saleable child variants."
        actions={
          <form className="workspace-search" onSubmit={onSearch}>
            <input
              type="search"
              value={queryInput}
              placeholder="Search by product, variant, SKU, barcode"
              onChange={(event) => setQueryInput(event.target.value)}
            />
            <button type="submit">Search</button>
          </form>
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !workspace ? <WorkspaceNotice>Loading catalog…</WorkspaceNotice> : null}

        {activeTab === 'products' ? (
          workspace?.items.length ? (
            <div className="workspace-card-grid">
              {workspace.items.map((product) => (
                <article key={product.product_id} className="commerce-card">
                  <div className="commerce-card-header">
                    <div>
                      <p className="eyebrow">Catalog Parent</p>
                      <h4>{product.name}</h4>
                      <p>{product.brand || 'No brand'} · {product.category || 'Uncategorized'} · {product.supplier || 'No supplier'}</p>
                    </div>
                    <button type="button" onClick={() => onProductEdit(product)}>Edit product</button>
                  </div>
                  <div className="commerce-card-meta">
                    <span>SKU Root: {product.sku_root || 'Not set'}</span>
                    <span>Base Price: {formatMoney(product.default_price)}</span>
                    <span>Variants: {product.variants.length}</span>
                  </div>
                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Variant</th>
                          <th>SKU</th>
                          <th>Available</th>
                          <th>Reserved</th>
                          <th>Price</th>
                          <th>Reorder</th>
                        </tr>
                      </thead>
                      <tbody>
                        {product.variants.map((variant) => (
                          <tr key={variant.variant_id}>
                            <td>{variant.label}</td>
                            <td>{variant.sku}</td>
                            <td>{formatQuantity(variant.available_to_sell)}</td>
                            <td>{formatQuantity(variant.reserved)}</td>
                            <td>{formatMoney(variant.unit_price)}</td>
                            <td>{formatQuantity(variant.reorder_level)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <WorkspaceEmpty
              title="No active in-stock catalog items"
              message="Use Add Product to create a parent product and its saleable variants."
            />
          )
        ) : (
          <form className="workspace-form" onSubmit={onSave}>
            <div className="workspace-form-grid">
              <label>
                Product name
                <input
                  value={form.identity.product_name}
                  onChange={(event) =>
                    setForm((current) => ({
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
                  list="catalog-suppliers"
                  value={form.identity.supplier}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      identity: { ...current.identity, supplier: event.target.value },
                    }))
                  }
                />
              </label>
              <label>
                Category
                <input
                  list="catalog-categories"
                  value={form.identity.category}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      identity: { ...current.identity, category: event.target.value },
                    }))
                  }
                />
              </label>
              <label>
                Brand
                <input
                  value={form.identity.brand}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      identity: { ...current.identity, brand: event.target.value },
                    }))
                  }
                />
              </label>
              <label>
                SKU root
                <input
                  value={form.identity.sku_root}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      identity: { ...current.identity, sku_root: event.target.value },
                    }))
                  }
                />
              </label>
              <label>
                Default price
                <input
                  value={form.identity.default_selling_price}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      identity: { ...current.identity, default_selling_price: event.target.value },
                    }))
                  }
                />
              </label>
              <label>
                Minimum price
                <input
                  value={form.identity.min_selling_price}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      identity: { ...current.identity, min_selling_price: event.target.value },
                    }))
                  }
                />
              </label>
              <label>
                Max discount %
                <input
                  value={form.identity.max_discount_percent}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      identity: { ...current.identity, max_discount_percent: event.target.value },
                    }))
                  }
                />
              </label>
            </div>

            <label>
              Description
              <textarea
                rows={3}
                value={form.identity.description}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    identity: { ...current.identity, description: event.target.value },
                  }))
                }
              />
            </label>

            <div className="workspace-subsection">
              <div className="workspace-subsection-header">
                <div>
                  <h4>Variants</h4>
                  <p>Every saleable option must have its own variant row and SKU.</p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setForm((current) => ({
                      ...current,
                      variants: [...current.variants, { ...EMPTY_VARIANT }],
                    }))
                  }
                >
                  Add variant
                </button>
              </div>

              <div className="workspace-stack">
                {form.variants.map((variant, index) => (
                  <div key={`${variant.variant_id ?? 'new'}-${index}`} className="variant-editor">
                    <div className="workspace-form-grid compact">
                      <label>
                        Size
                        <input
                          value={variant.size}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index ? { ...item, size: event.target.value } : item
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        Color
                        <input
                          value={variant.color}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index ? { ...item, color: event.target.value } : item
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        Other
                        <input
                          value={variant.other}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index ? { ...item, other: event.target.value } : item
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        SKU
                        <input
                          value={variant.sku}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index ? { ...item, sku: event.target.value } : item
                              ),
                            }))
                          }
                          required
                        />
                      </label>
                      <label>
                        Barcode
                        <input
                          value={variant.barcode}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index ? { ...item, barcode: event.target.value } : item
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        Cost
                        <input
                          value={variant.default_purchase_price}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, default_purchase_price: event.target.value }
                                  : item
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        Price
                        <input
                          value={variant.default_selling_price}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, default_selling_price: event.target.value }
                                  : item
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        Min price
                        <input
                          value={variant.min_selling_price}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index ? { ...item, min_selling_price: event.target.value } : item
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        Reorder level
                        <input
                          value={variant.reorder_level}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              variants: current.variants.map((item, itemIndex) =>
                                itemIndex === index ? { ...item, reorder_level: event.target.value } : item
                              ),
                            }))
                          }
                        />
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="workspace-actions">
              <button type="submit">{form.product_id ? 'Update product' : 'Create product'}</button>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    identity: { ...EMPTY_IDENTITY },
                    variants: [{ ...EMPTY_VARIANT }],
                  })
                }
              >
                Reset
              </button>
            </div>

            <datalist id="catalog-suppliers">
              {workspace?.suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.name} />)}
            </datalist>
            <datalist id="catalog-categories">
              {workspace?.categories.map((category) => <option key={category.category_id} value={category.name} />)}
            </datalist>
          </form>
        )}
      </WorkspacePanel>
    </div>
  );
}
