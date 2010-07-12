
class ReversionRouter(object):
    def db_for_read(self, model, **hints):
        affinity = getattr(model, 'db_affinity', None)
        return affinity

    def db_for_write(self, model, **hints):
        affinity = getattr(model, 'db_affinity', None)
        return affinity

    def allow_syncdb(self, db, model):
        affinity = getattr(model, 'db_affinity', None)
        if db == 'reversion':
            return affinity == 'reversion'
        if affinity == 'reversion':
            return db == affinity
