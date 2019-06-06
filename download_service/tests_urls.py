from django.core.urlresolvers import reverse
from django.test.testcases import TestCase
from django.urls.exceptions import NoReverseMatch


class DownloadUrlTestCase(TestCase):
    def setUp(self):
        self.name = 'download-dds-project-zip'

    def test_resolves_download_url(self):
        resolved = reverse(self.name, kwargs={'project_id': '6ee7ff4b-da91-4cff-ab67-4693d701060d', 'filename': 'ProjectABC.zip'})
        self.assertEqual(resolved, '/download/dds-projects/6ee7ff4b-da91-4cff-ab67-4693d701060d/ProjectABC.zip')

    def test_raises_with_no_params(self):
        with self.assertRaises(NoReverseMatch):
            reverse(self.name)

    def test_raises_with_other_params(self):
        with self.assertRaises(NoReverseMatch):
            reverse(self.name, kwargs={'file_id': 'some-id'})
