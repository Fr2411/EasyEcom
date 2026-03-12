from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from easy_ecom.data.store.postgres_db import Base
from easy_ecom.data.store.postgres_models import InventoryTxnModel, ProductModel, ProductVariantModel
from easy_ecom.domain.services.saleable_items_service import SaleableItemsService


def test_saleable_items_service_search_and_stock():
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with sf() as s:
        s.add(ProductModel(product_id='p1', client_id='c1', product_name='Red Tee', is_active='true'))
        s.add(ProductVariantModel(variant_id='v1', client_id='c1', parent_product_id='p1', variant_name='Size:M', sku_code='REDTEE-001', barcode='BAR-1', is_active='true', default_selling_price='99'))
        s.add(InventoryTxnModel(txn_id='t1', client_id='c1', txn_type='IN', product_id='p1', variant_id='v1', qty='5'))
        s.add(InventoryTxnModel(txn_id='t2', client_id='c1', txn_type='OUT', product_id='p1', variant_id='v1', qty='2'))
        s.commit()

    svc = SaleableItemsService()
    with sf() as s:
        by_sku = svc.list_saleable_variants(session=s, client_id='c1', query='REDTEE', include_out_of_stock=False)
        by_name = svc.list_saleable_variants(session=s, client_id='c1', query='Red Tee', include_out_of_stock=False)
        by_barcode = svc.list_saleable_variants(session=s, client_id='c1', query='BAR-1', include_out_of_stock=False)

    assert by_sku and by_name and by_barcode
    assert by_sku[0]['variant_id'] == 'v1'
    assert by_sku[0]['available_qty'] == 3.0
    assert by_sku[0]['sku'] == 'REDTEE-001'
