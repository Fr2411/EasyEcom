from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from easy_ecom.data.store.postgres_models import (
    AiReviewDraftModel,
    AutomationDecisionModel,
    Base,
    ChannelConversationModel,
    ChannelIntegrationModel,
    ChannelMessageModel,
)
from easy_ecom.domain.services.automation_service import AutomationPolicyPatch, AutomationService


class StubDraftGenerator:
    def __init__(self, confidence: str = 'grounded') -> None:
        self.confidence = confidence

    def generate(self, *, client_id: str, inbound_message: str):
        return {
            'draft_text': f'Reply for {inbound_message}',
            'intent': 'pricing_lookup',
            'confidence': self.confidence,
            'grounding': {'source': 'test'},
        }


class StubAiReviewService:
    def __init__(self, confidence: str = 'grounded') -> None:
        self.draft_generator = StubDraftGenerator(confidence=confidence)


class StubIntegrationsService:
    def prepare_outbound(self, **kwargs):
        return {'status': 'prepared'}


def _build_service(confidence: str = 'grounded'):
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with sf() as s:
        s.add(ChannelIntegrationModel(channel_id='chl-1', client_id='tenant-a', provider='webhook', display_name='Web', status='active', external_account_id='', verify_token='v', inbound_secret='sec', config_json='{}', created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z', created_by_user_id='u1', last_inbound_at=''))
        s.add(ChannelConversationModel(conversation_id='conv-1', client_id='tenant-a', channel_id='chl-1', external_sender_id='wa-1', status='open', customer_id='', linked_sale_id='', created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z', last_message_at='2026-01-01T00:00:00Z'))
        s.add(ChannelMessageModel(message_id='msg-1', client_id='tenant-a', channel_id='chl-1', conversation_id='conv-1', direction='inbound', provider_event_id='e1', external_sender_id='wa-1', message_text='what is the price?', content_summary='price', payload_json='{}', occurred_at='2026-01-01T00:00:00Z', created_at='2026-01-01T00:00:00Z', outbound_status='received', created_by_user_id=''))
        s.commit()

    return AutomationService(sf, ai_review_service=StubAiReviewService(confidence=confidence), integrations_service=StubIntegrationsService()), sf


def test_policy_enable_disable_and_patch() -> None:
    service, _ = _build_service()
    policy = service.get_policy(client_id='tenant-a')
    assert policy['automation_enabled'] is False

    enabled = service.enable(client_id='tenant-a', updated_by_user_id='u1')
    assert enabled['automation_enabled'] is True

    patched = service.patch_policy(client_id='tenant-a', updated_by_user_id='u1', payload=AutomationPolicyPatch(auto_send_enabled=True, categories={'business_hours_basic_info': True}))
    assert patched['auto_send_enabled'] is True
    assert patched['categories']['business_hours_basic_info'] is True


def test_run_autosend_vs_fallback_draft_and_audit() -> None:
    service, sf = _build_service(confidence='grounded')
    service.patch_policy(client_id='tenant-a', updated_by_user_id='u1', payload=AutomationPolicyPatch(automation_enabled=True, auto_send_enabled=True))

    sent = service.run(client_id='tenant-a', conversation_id='conv-1', run_by_user_id='u1')
    assert sent['outcome'] == 'auto_sent'

    with sf() as s:
        decisions = s.execute(select(AutomationDecisionModel)).scalars().all()
        assert len(decisions) == 1

    low_conf_service, sf2 = _build_service(confidence='insufficient_context')
    low_conf_service.patch_policy(client_id='tenant-a', updated_by_user_id='u1', payload=AutomationPolicyPatch(automation_enabled=True, auto_send_enabled=True))
    drafted = low_conf_service.run(client_id='tenant-a', conversation_id='conv-1', run_by_user_id='u1')
    assert drafted['outcome'] == 'drafted'

    with sf2() as s:
        drafts = s.execute(select(AiReviewDraftModel)).scalars().all()
        assert len(drafts) == 1


def test_unsupported_message_escalates_to_human_review_queue() -> None:
    service, sf = _build_service()
    with sf() as s:
        s.add(ChannelConversationModel(conversation_id='conv-2', client_id='tenant-a', channel_id='chl-1', external_sender_id='wa-2', status='open', customer_id='', linked_sale_id='', created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z', last_message_at='2026-01-01T00:00:00Z'))
        s.add(ChannelMessageModel(message_id='msg-2', client_id='tenant-a', channel_id='chl-1', conversation_id='conv-2', direction='inbound', provider_event_id='e2', external_sender_id='wa-2', message_text='need custom enterprise plan', content_summary='custom', payload_json='{}', occurred_at='2026-01-01T00:00:00Z', created_at='2026-01-01T00:00:00Z', outbound_status='received', created_by_user_id=''))
        s.commit()

    service.patch_policy(client_id='tenant-a', updated_by_user_id='u1', payload=AutomationPolicyPatch(automation_enabled=True, auto_send_enabled=True))
    result = service.run(client_id='tenant-a', conversation_id='conv-2', run_by_user_id='u1')
    assert result['outcome'] == 'escalated'

    queue = service.list_queue(client_id='tenant-a')
    assert queue[0]['conversation_id'] == 'conv-2'
