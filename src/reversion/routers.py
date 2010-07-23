from django.conf import settings

class ReversionRouter(object):
    def db_for_read(self, model, **hints):
        affinity = getattr(model, 'db_affinity', None)
        return affinity

    def db_for_write(self, model, **hints):
        affinity = getattr(model, 'db_affinity', None)
        return affinity

    def allow_syncdb(self, db, model):
        affinity = getattr(model, 'db_affinity', None)
        reversion_db = getattr(settings, 'REVERSION_DB', 'default')
        return (db == reversion_db and affinity == reversion_db)
