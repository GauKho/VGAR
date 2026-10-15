"""Explicit generator modes. Fake output is never a fallback for a real error."""
class FakeGenerator:
    mode = 'fake'
    def __init__(self, raw_text):
        self.raw_text = raw_text

    def generate(self, prompt, profile, timeout_seconds):
        return dict(status='PASS', mode='fake', raw_text=self.raw_text, finish_reason='fixture',
                    truncated=False, input_tokens=prompt.input_tokens, output_tokens=None,
                    token_measurement='unit-test-only', duration_ms=0)

