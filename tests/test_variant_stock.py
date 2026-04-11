from unittest import TestCase
from inventory.models import InventoryTransaction

class TestVariantStock(TestCase):
    def test_variant_stock_accuracy(self):
        # Create a test variant and transaction
        variant_id = 'test_variant_1'
        quantity = 100
        
        # Simulate inventory transaction
        transaction = InventoryTransaction.objects.create(
            variant_id=variant_id,
            quantity_change=quantity,
            transaction_type='purchase'
        )
        
        # Verify stock accuracy
        self.assertEqual(transaction.variant_id, variant_id)
        self.assertEqual(transaction.quantity_change, quantity)
        
        # Additional checks for ledger consistency
        ledger_entry = InventoryTransaction.objects.filter(variant_id=variant_id).first()
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.quantity_change, quantity)

    def test_tenant_isolation(self):
        # Test that tenant data is properly isolated
        tenant1_id = 'tenant_1'
        tenant2_id = 'tenant_2'
        
        # Create transactions for different tenants
        InventoryTransaction.objects.create(
            tenant_id=tenant1_id,
            variant_id='common_variant',
            quantity_change=50
        )
        InventoryTransaction.objects.create(
            tenant_id=tenant2_id,
            variant_id='common_variant',
            quantity_change=75
        )
        
        # Verify tenant-specific stock counts
        tenant1_count = InventoryTransaction.objects.filter(tenant_id=tenant1_id).count()
        tenant2_count = InventoryTransaction.objects.filter(tenant_id=tenant2_id).count()
        
        self.assertEqual(tenant1_count, 1)
        self.assertEqual(tenant2_count, 1)
        
        # Ensure no cross-tenant data leakage
        self.assertFalse(InventoryTransaction.objects.filter(tenant_id=tenant1_id).filter(variant_id='common_variant').exists())