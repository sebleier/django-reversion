from __future__ import with_statement

import datetime, unittest

from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import models, transaction

import reversion
from reversion.admin import VersionAdmin
from reversion.helpers import patch_admin
from reversion.models import Version, Revision


try:
    from reversion.helpers import generate_patch, generate_patch_html
except ImportError:
    pass
else:
    
    class PatchTest(unittest.TestCase):
        
        """Tests the patch generation functionality."""
        
        def setUp(self):
            """Sets up a versioned site model to test."""
            reversion.register(Site)
            with reversion.revision:
                site = Site.objects.create(name="site", domain="www.site-rev-1.com")
            with reversion.revision:
                site.domain = "www.site-rev-2.com"
                site.save()
            self.site = site
        
        def testCanGeneratePatch(self):
            """Tests that text and HTML patches can be generated."""
            version_0 = Version.objects.get_for_object(self.site)[0]
            version_1 = Version.objects.get_for_object(self.site)[1]
            self.assertEqual(generate_patch(version_0, version_1, "domain"),
                             "@@ -10,9 +10,9 @@\n rev-\n-1\n+2\n .com\n")
            self.assertEqual(generate_patch_html(version_0, version_1, "domain"),
                             u'<SPAN TITLE="i=0">www.site-rev-</SPAN><DEL STYLE="background:#FFE6E6;" TITLE="i=13">1</DEL><INS STYLE="background:#E6FFE6;" TITLE="i=13">2</INS><SPAN TITLE="i=14">.com</SPAN>')
        
        def tearDown(self):
            """Deletes the versioned site model."""
            reversion.unregister(Site)
            self.site.delete()
            Version.objects.all().delete()
            
            
