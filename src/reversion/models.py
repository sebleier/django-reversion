"""Database models used by Reversion."""


from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.db import models
from reversion import fields
import reversion
from reversion.managers import VersionManager
from django.conf import settings

class ReversionUserManager(models.Manager):

    def get_by_natural_key(self, *args):
        return self.get(username=args[0])

class ReversionUser(User):
    objects = ReversionUserManager()

    def natural_key(self):
        return (self.username,)

    class Meta:
        proxy = True

class RevisionNaturalKeyBase(models.Model):
    user = fields.NaturalKey(ReversionUser,
                             blank=True,
                             null=True,
                             help_text="The user who created this revision.")
    class Meta:
        abstract = True

class RevisionForeignKeyBase(models.Model):
    user = models.ForeignKey(User,
                             blank=True,
                             null=True,
                             help_text="The user who created this revision.")
    class Meta:
        abstract = True
    

class VersionNaturalKeyBase(models.Model):
    content_type = fields.NaturalKey(ContentType,
                                     help_text="Content type of the model under version control.")
    class Meta:
        abstract = True

class VersionForeignKeyBase(models.Model):
    content_type = models.ForeignKey(ContentType,
                                     help_text="Content type of the model under version control.")
    class Meta:
        abstract = True


def get_revision_base():
    if getattr(settings, 'REVERSION_USE_MULTI_DB', False):
        return RevisionNaturalKeyBase
    return RevisionForeignKeyBase

def get_version_base():
    if getattr(settings, 'REVERSION_USE_MULTI_DB', False):
        return VersionNaturalKeyBase
    return VersionForeignKeyBase

class Revision(get_revision_base()):
    
    """A group of related object versions."""

    db_affinity = getattr(settings, 'REVERSION_DB', 'default') 
    
    date_created = models.DateTimeField(auto_now_add=True,
                                        help_text="The date and time this revision was created.", db_index=True)
    
    comment = models.TextField(blank=True,
                               help_text="A text comment on this revision.")
    
    def revert(self, delete=False):
        """Reverts all objects in this revision."""
        versions = self.version_set.all()
        for version in versions:
            version.revert()
        if delete:
            # Get a set of all objects in this revision.
            old_revision_set = [ContentType.objects.get_for_id(version.content_type_id).get_object_for_this_type(pk=version.object_id)
                                    for version in versions]
            # Calculate the set of all objects that are in the revision now.
            current_revision_set = reversion.revision.follow_relationships(old_revision_set)
            # Delete objects that are no longer in the current revision.
            for current_object in current_revision_set:
                if not current_object in old_revision_set:
                    current_object.delete()
            
    def __unicode__(self):
        """Returns a unicode representation."""
        return u", ".join([unicode(version)
                           for version in self.version_set.all()])
            

class Version(get_version_base()):
    
    """A saved version of a database model."""
    
    db_affinity = getattr(settings, 'REVERSION_DB', 'default') 
    objects = VersionManager()
    
    revision = models.ForeignKey(Revision,
                                 help_text="The revision that contains this version.")
    
    object_id = models.TextField(help_text="Primary key of the model under version control.", db_index=True)
    
    format = models.CharField(max_length=255,
                              help_text="The serialization format used by this model.")
    
    serialized_data = models.TextField(help_text="The serialized form of this version of the model.")
    
    object_repr = models.TextField(help_text="A string representation of the object.")

    is_deleted = models.BooleanField(default=False)
    
    def get_object_version(self):
        """Returns the stored version of the model."""
        data = self.serialized_data
        if isinstance(data, unicode):
            data = data.encode("utf8")
        return list(serializers.deserialize(self.format, data))[0]
    
    object_version = property(get_object_version,
                              doc="The stored version of the model.")
       
    def get_field_dict(self):
        """
        Returns a dictionary mapping field names to field values in this version
        of the model.
        
        This method will follow parent links, if present.
        """
        if not hasattr(self, "_field_dict_cache"):
            object_version = self.object_version
            obj = object_version.object
            result = {}
            for field in obj._meta.fields:
                result[field.name] = field.value_from_object(obj)
            result.update(object_version.m2m_data)
            # Add parent data.
            for parent_class, field in obj._meta.parents.items():
                content_type = ContentType.objects.get_for_model(parent_class)
                if field:
                    parent_id = unicode(getattr(obj, field.attname))
                else:
                    parent_id = obj.pk
                try:
                    parent_version = Version.objects.get(revision__id=self.revision_id,
                                                         content_type=content_type,
                                                         object_id=parent_id)
                except parent_class.DoesNotExist:
                    pass
                else:
                    result.update(parent_version.get_field_dict())
            setattr(self, "_field_dict_cache", result)
        return getattr(self, "_field_dict_cache")
       
    field_dict = property(get_field_dict,
                          doc="A dictionary mapping field names to field values in this version of the model.")
       
    def revert(self):
        """Recovers the model in this version."""
        self.object_version.save()
        
    def __unicode__(self):
        """Returns a unicode representation."""
        return self.object_repr
    
    
