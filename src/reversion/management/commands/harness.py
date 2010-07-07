
import sys
import os
import gzip
import zipfile
from optparse import make_option

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connections, router, transaction, DEFAULT_DB_ALIAS
from django.db.models import get_apps

class Command(BaseCommand):
    help = 'Attempts to create N revisions of N apps.'
    args = 'app1.model1 app2.model2 ...appN.modelN'

    option_list = BaseCommand.option_list + (
        make_option('--number', action='store', dest='number',
            default='2000', help='Number of revisions to attempt to create.'),
    )

    def handle(self, *apps, **options):
        pass 

