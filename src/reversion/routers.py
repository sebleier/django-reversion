
class ReversionRouter(object):
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'reversion' and not model._meta.proxy:
            return 'reversion'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'reversion' and not model._meta.proxy:
            return 'reversion'

    def allow_syncdb(self, db, model):
        if model._meta.app_label == 'reversion' and not model._meta.proxy:
            return db == 'reversion'
        return db == 'default' 
