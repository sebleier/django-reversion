import sys
import os
import hashlib
import datetime
from optparse import make_option

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connections, router, transaction, DEFAULT_DB_ALIAS
from django.db.models import get_apps
from django.utils.importlib import import_module
from reversion.revisions import revision

class Command(BaseCommand):
    help = 'Attempts to create N revisions of a model.'
    args = 'app.models.Model:creation_fn'

    option_list = BaseCommand.option_list + (
        make_option('--number', '-n', action='store', dest='number',
            default='2000', help='Number of revisions to attempt to create.'),
    )

    def handle(self, *apps, **options):
        get_module_and_target = lambda x : x.rsplit('.', 1)
        def load_module_and_target(mod, target):
            module = import_module(mod)
            target, pk = target.split(':')
            model = getattr(module, target)
            return model, pk 
        models = [load_module_and_target(module, target) for module, target in (get_module_and_target(app) for app in apps)]
        number = int(options['number'])
        comment = hashlib.md5(str(datetime.datetime.now())).hexdigest()
        print "About to create %d revisions of %d models." % (number, len(models))
        print "to remove these revisions, use Revision.objects.filter(comment='%s').delete()" % comment
        [revision.register(model) for model, creation in models]

        for i in range(number):
            for model, pk in models:
                revision.start()
                try:
                    revision.comment = comment
                    model = model.objects.get(pk=pk)
                    model.save()
                    sys.stdout.write('.')
                except:
                    revision.invalidate()
                    raise
                finally:
                    revision.end()
            sys.stdout.flush()
        print "finished."

