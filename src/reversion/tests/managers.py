from django.test import TestCase
from django.contrib.auth.models import User
from reversion.revisions import revision
from reversion.models import Revision, Version 
import random
import datetime

class TestOfManager(TestCase):
    def tearDown(self):
        try:
            revision.unregister(User)
        except:
            pass

    def test_get_for_object_reference_returns_appropriate_versions(self):
        user = User.objects.create(
            username='random-%d' % random.randint(1, 100),
            email='admin@admin.com',
        )
        random_number_of_versions = random.randint(1, 100)
        revision.register(User)
        for i in range(random_number_of_versions):
            try:
                revision.start()
                user.username = 'random-%d' % i
                user.save()
            except:
                revision.invalidate()
            finally:
                revision.end()
        versions = Version.objects.get_for_object_reference(User, user.pk)
        self.assertEqual(len(versions), random_number_of_versions)

    def test_get_for_object_returns_appropriate_versions(self):
        user = User.objects.create(
            username='random-%d' % random.randint(1, 100),
            email='admin@admin.com',
        )
        random_number_of_versions = random.randint(1, 100)
        revision.register(User)
        for i in range(random_number_of_versions):
            try:
                revision.start()
                user.username = 'random-%d' % i
                user.save()
            except:
                revision.invalidate()
            finally:
                revision.end()
        versions = Version.objects.get_for_object(user)
        self.assertEqual(len(versions), random_number_of_versions)

    def test_get_unique_for_object_returns_appropriate_versions(self):
        user = User.objects.create(
            username='random-%d' % random.randint(2, 100),
            email='admin@admin.com',
        )

        # make sure the random number is evenly divisible
        random_number_of_versions = abs(random.randint(2, 50) & (~0<<1)) 
        revision.register(User)
        user = User.objects.get(email='admin@admin.com')
        for i in range(random_number_of_versions/2):
            try:
                revision.start()
                user.username = 'sequential-%d' % i
                user.save()
            except:
                revision.invalidate()
            finally:
                revision.end()

        for i in range(random_number_of_versions/2, 0, -1):
            try:
                revision.start()
                user.username = 'sequential-%d' % i
                user.save()
            except:
                revision.invalidate()
            finally:
                revision.end()

        versions = Version.objects.get_unique_for_object(user)
        self.assertEqual(len(versions), random_number_of_versions)

    def test_get_for_date_raises_does_not_exist_on_none_available(self):
        user = User.objects.create(
            username='rand-%d' % random.randint(1, 100),
        )
        revision.register(User)
        self.assertRaises(Version.DoesNotExist, Version.objects.get_for_date, user, datetime.datetime.now()) 

    def test_get_for_date_returns_version_if_one_is_available(self):
        revision.register(User)
        try:
            revision.start()
            user = User.objects.create(
                username='rand-%d' % random.randint(1, 100),
            )
        except:
            revision.invalidate()
        finally:
            revision.end()
        now = datetime.datetime.now()
        version = Version.objects.get_for_date(user, now) 
        self.assertTrue(version.revision.date_created <= now) 

    def test_get_deleted_object_raises_does_not_exist_on_none_available(self):
        user = User.objects.create(
            username='rand-%d' % random.randint(1, 100),
        )
        pk = user.pk
        user.delete()
        revision.register(User)
        self.assertRaises(Version.DoesNotExist, Version.objects.get_deleted_object, User, pk) 

    def test_get_deleted_object_returns_version_if_one_is_available(self):
        revision.register(User)
        pk = None
        try:
            revision.start()
            user = User.objects.create(
                username='rand-%d' % random.randint(1, 100),
            )
            pk = user.pk
        except:
            revision.invalidate()
        finally:
            revision.end()
        try:
            revision.start()
            user.delete()
        except:
            revision.invalidate()
        finally:
            revision.end()
        version = Version.objects.get_deleted_object(User, pk)
        self.assertEqual(version.object_version.object.pk, pk) 

    def test_get_deleted_returns_appropriate_list_of_deleted_objects_for_model(self):
        revision.register(User)
        random_number_of_users = random.randint(1, 100)
        for i in range(random_number_of_users):
            user = None
            try:
                revision.start()
                user = User.objects.create(
                    username='sequential-%d' % i
                )
            except:
                revision.invalidate()
            finally:
                revision.end()
        try:
            revision.start()
            User.objects.all().delete()
        except:
            revision.invalidate()
        finally:
            revision.end()

        deleted = Version.objects.get_deleted(User)
        self.assertEqual(len(deleted), random_number_of_users)

