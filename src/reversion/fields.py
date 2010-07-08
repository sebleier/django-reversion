from django.db.models.fields import TextField
from django.utils import simplejson
from django.db.models.fields.related import *

class NaturalModelChoiceField(forms.ModelChoiceField):
    def to_python(self, value):
        return self.queryset.model._default_manager.get_by_natural_key(*simplejson.loads(value))

    def _get_choices(self):
        iter = super(NaturalModelChoiceField, self)._get_choices()
        class NaturalModelChoiceIterator(iter.__class__):
            def choice(self, obj):
                return (simplejson.dumps(obj.natural_key()), self.field.label_from_instance(obj))
        return NaturalModelChoiceIterator(self) 

    choices = property(_get_choices, forms.ChoiceField._set_choices)

class NaturalManyToOneRel(ManyToOneRel):
    field_name = None

    def is_hidden(self):
        return False

    def __init__(self, to, related_name=None, limit_choices_to=None, 
        lookup_overrides=None, parent_link=False):
        base = to
        if to._meta.proxy:
            for i in to.mro():
                if not i._meta.proxy:
                    base = i
                    break

        self.base_class = base 
        self.to = to
        self.related_name = related_name
        self.lookup_overrides = lookup_overrides or {}
        self.multiple = True
        self.parent_link = parent_link 
        self.limit_choices_to = limit_choices_to or {}

    

class ReverseSingleNaturalObjectDescriptor(object):
    # This class provides the functionality that makes the related-object
    # managers available as attributes on a model class, for fields that have
    # a single "remote" value, on the class that defines the related field.
    # In the example "choice.poll", the poll attribute is a
    # ReverseSingleRelatedObjectDescriptor instance.
    def __init__(self, field_with_rel):
        self.field = field_with_rel

    def __get__(self, instance, instance_type=None):
        if instance is None:
            return self

        cache_name = self.field.get_cache_name()
        try:
            return getattr(instance, cache_name)
        except AttributeError:
            val = getattr(instance, self.field.attname)
            if val is None:
                # If NULL is an allowed value, return it.
                if self.field.null:
                    return None
                raise self.field.rel.to.DoesNotExist
            natural_key = simplejson.loads(val)
            rel_mgr = self.field.rel.to._default_manager
            return rel_mgr.get_by_natural_key(*natural_key)

    def __set__(self, instance, value):
        if instance is None:
            raise AttributeError("%s must be accessed via instance" % self._field.name)

        if isinstance(value, self.field.rel.base_class):
            value.__class__ = self.field.rel.to

        # If null=True, we can assign null here, but otherwise the value needs
        # to be an instance of the related class.
        if value is None and self.field.null == False:
            raise ValueError('Cannot assign None: "%s.%s" does not allow null values.' %
                                (instance._meta.object_name, self.field.name))
        elif value is not None and not isinstance(value, (self.field.rel.to, basestring)):
            raise ValueError('Cannot assign "%r": "%s.%s" must be a "%s" instance.' %
                                (value, instance._meta.object_name,
                                 self.field.name, self.field.rel.to._meta.object_name))
        elif value is not None:
            if isinstance(value, basestring):
                value = self.field.rel.to._default_manager.get_by_natural_key(*simplejson.loads(value))

            if instance._state.db is None:
                instance._state.db = router.db_for_write(instance.__class__, instance=value)
            elif value._state.db is None:
                value._state.db = router.db_for_write(value.__class__, instance=instance)
        # If we're setting the value of a OneToOneField to None, we need to clear
        # out the cache on any old related object. Otherwise, deleting the
        # previously-related object will also cause this object to be deleted,
        # which is wrong.
        if value is None:
            # Look up the previously-related object, which may still be available
            # since we've not yet cleared out the related field.
            # Use the cache directly, instead of the accessor; if we haven't
            # populated the cache, then we don't care - we're only accessing
            # the object to invalidate the accessor cache, so there's no
            # need to populate the cache just to expire it again.
            related = getattr(instance, self.field.get_cache_name(), None)

            # If we've got an old related object, we need to clear out its
            # cache. This cache also might not exist if the related object
            # hasn't been accessed yet.
            if related:
                cache_name = self.field.related.get_cache_name()
                try:
                    delattr(related, cache_name)
                except AttributeError:
                    pass

        # Set the value of the related field
        try:
            val = simplejson.dumps(value.natural_key())
        except AttributeError:
            val = None
        setattr(instance, self.field.column, val)

        # Since we already know what the related object is, seed the related
        # object cache now, too. This avoids another db hit if you get the
        # object you just set.
        setattr(instance, self.field.get_cache_name(), value)

class ForeignNaturalObjectsDescriptor(object):
    # This class provides the functionality that makes the related-object
    # managers available as attributes on a model class, for fields that have
    # multiple "remote" values and have a ForeignKey pointed at them by
    # some other model. In the example "poll.choice_set", the choice_set
    # attribute is a ForeignRelatedObjectsDescriptor instance.
    def __init__(self, related):
        self.related = related   # RelatedObject instance

    def __get__(self, instance, instance_type=None):
        if instance is None:
            return self

        return self.create_manager(instance,
                self.related.model._default_manager.__class__)

    def __set__(self, instance, value):
        if instance is None:
            raise AttributeError("Manager must be accessed via instance")

        manager = self.__get__(instance)
        # If the foreign key can support nulls, then completely clear the related set.
        # Otherwise, just move the named objects into the set.
        if self.related.field.null:
            manager.clear()
        manager.add(*value)

    def delete_manager(self, instance):
        """
        Returns a queryset based on the related model's base manager (rather
        than the default manager, as returned by __get__). Used by
        Model.delete().
        """
        return self.create_manager(instance,
                self.related.model._base_manager.__class__)

    def create_manager(self, instance, superclass):
        """
        Creates the managers used by other methods (__get__() and delete()).
        """
        rel_field = self.related.field
        rel_model = self.related.model

        class RelatedManager(superclass):
            def get_query_set(self):
                db = self._db or router.db_for_read(rel_model, instance=instance)
                return superclass.get_query_set(self).using(db).filter(**(self.core_filters))

            def add(self, *objs):
                for obj in objs:
                    if not isinstance(obj, self.model):
                        raise TypeError("'%s' instance expected" % self.model._meta.object_name)
                    setattr(obj, rel_field.name, instance)
                    obj.save()
            add.alters_data = True

            def create(self, **kwargs):
                kwargs.update({rel_field.name: instance})
                db = router.db_for_write(rel_model, instance=instance)
                return super(RelatedManager, self).using(db).create(**kwargs)
            create.alters_data = True

            def get_or_create(self, **kwargs):
                # Update kwargs with the related object that this
                # ForeignRelatedObjectsDescriptor knows about.
                kwargs.update({rel_field.name: instance})
                db = router.db_for_write(rel_model, instance=instance)
                return super(RelatedManager, self).using(db).get_or_create(**kwargs)
            get_or_create.alters_data = True

            # remove() and clear() are only provided if the ForeignKey can have a value of null.
            if rel_field.null:
                def remove(self, *objs):
                    val = getattr(instance, rel_field.rel.get_related_field().attname)
                    for obj in objs:
                        # Is obj actually part of this descriptor set?
                        if getattr(obj, rel_field.attname) == val:
                            setattr(obj, rel_field.name, None)
                            obj.save()
                        else:
                            raise rel_field.rel.to.DoesNotExist("%r is not related to %r." % (obj, instance))
                remove.alters_data = True

                def clear(self):
                    for obj in self.all():
                        setattr(obj, rel_field.name, None)
                        obj.save()
                clear.alters_data = True

        manager = RelatedManager()
        manager.core_filters = {rel_field.name:instance}
        manager.model = self.related.model
        return manager
 

class NaturalKey(ForeignKey):
    def __init__(self, to, *args, **kwargs):
        kwargs = {
            'verbose_name':kwargs.get('verbose_name', None),
            'null':kwargs.get('null', None),
            'blank':kwargs.get('blank', None),
            'rel': NaturalManyToOneRel(to,
                related_name=kwargs.pop('related_name', None),
                lookup_overrides=kwargs.pop('lookup_overrides', None),
                parent_link=kwargs.pop('parent_link', False),
                limit_choices_to=kwargs.pop('limit_choices_to', None),
            ),
        }
        kwargs['verbose_name'] = kwargs.get('verbose_name', None)
        Field.__init__(self, **kwargs)        
        self.db_index = True

    def validate(self, value, model_instance):
        if self.rel.parent_link:
            return
        if value is None:
            return
        try:
            if isinstance(value, basestring):
                value = simplejson.loads(value)
            obj = self.rel.to._default_manager.get_by_natural_key(*value)
        except self.rel.to.DoesNotExist:
            raise exceptions.ValidationError(self.error_messages['invalid'] % {
                'model':self.rel.to._meta.verbose_name, 'pk':value})

    def get_attname(self):
        return '%s_nk' % self.name

    def get_validator_unique_lookup_type(self):
        return '%s__exact' % (self.name)  

    def get_db_prep_save(self, value, connection):
        if value == '' or value == None:
            return None
        if isinstance(value, (list, tuple)):
            return simplejson.dumps(value)
        return value

    def value_to_string(self, obj):
        return Field.value_to_string(self, obj)

    def get_default(self):
        return ""

    def contribute_to_class(self, cls, name):
        super(ForeignKey, self).contribute_to_class(cls, name)
        setattr(cls, self.name, ReverseSingleNaturalObjectDescriptor(self))
        if isinstance(self.rel.to, basestring):
            target = self.rel.to
        else:
            target = self.rel.to._meta.db_table
        cls._meta.duplicate_targets[self.column] = (target, "o2m")

    def contribute_to_related_class(self, cls, related):
        setattr(cls, related.get_accessor_name(), ForeignNaturalObjectsDescriptor(related))

    def formfield(self, **kwargs):
        db = kwargs.pop('using', None)
        defaults = {
            'form_class': NaturalModelChoiceField,
            'queryset': self.rel.to._default_manager.using(db).complex_filter(self.rel.limit_choices_to),
            'to_field_name': 'pk',
        }
        defaults.update(kwargs)
        return super(ForeignKey, self).formfield(**defaults)

    def get_prep_lookup(self, lookup_type, value):
        if isinstance(value, self.rel.to):
            return simplejson.dumps(value.natural_key())
        if lookup_type in ('in',):
            return [self.get_prep_lookup('exact', v) for v in value]
        return super(NaturalKey, self).get_prep_lookup(lookup_type, value)

    def db_type(self, connection):
        # yeah, it's always a textfield. deal with it.
        return TextField().db_type(connection=connection)
