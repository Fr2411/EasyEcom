from __future__ import annotations

import unittest

from easy_ecom.api.routers import ai as ai_router


class AIRouterRenderingTests(unittest.TestCase):
    def test_render_public_chat_page_uses_tenant_assistant_name_and_opening_message(self) -> None:
        html = ai_router.render_public_chat_page_html(
            api_base_url="https://api.easy-ecom.online",
            widget_key="widget-123",
            assistant_name="Lina",
            opening_message="Hi! I can help with stock, prices, and orders.",
        )

        self.assertIn("Lina", html)
        self.assertIn("Hi! I can help with stock, prices, and orders.", html)
        self.assertIn("widget-123", html)
        self.assertIn("https://api.easy-ecom.online", html)

    def test_render_public_chat_page_escapes_script_breakout_in_opening_message(self) -> None:
        html = ai_router.render_public_chat_page_html(
            api_base_url="https://api.easy-ecom.online",
            widget_key="widget-123",
            assistant_name="Lina",
            opening_message='</script><script>alert(1)</script>',
        )

        self.assertNotIn('</script><script>alert(1)</script>', html)
        self.assertIn('<\\/script><script>alert(1)<\\/script>', html)


if __name__ == "__main__":
    unittest.main()
