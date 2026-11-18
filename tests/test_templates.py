"""템플릿 문법과 공통 필터. api 를 부르지 않는다 (CI 에서 api 없이 돈다)."""

from pathlib import Path

from django.template.loader import get_template
from django.test import SimpleTestCase

from web.templatetags import fmt

TEMPLATES = Path(__file__).resolve().parent.parent / "web" / "templates"


class TemplatesTest(SimpleTestCase):
    def test_all_templates_compile(self):
        names = [str(p.relative_to(TEMPLATES)) for p in TEMPLATES.rglob("*.html")]
        self.assertTrue(names)
        for name in names:
            with self.subTest(template=name):
                get_template(name)


class FiltersTest(SimpleTestCase):
    def test_pct_and_num(self):
        self.assertEqual(fmt.pct(0.5), "50%")
        self.assertEqual(fmt.num(1234567), "1,234,567")
