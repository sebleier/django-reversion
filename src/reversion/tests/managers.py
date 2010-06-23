from django.test import TestCase
from django.contrib.auth.models import User
import reversion
from reversion.models import Revision, Version 
import random
import datetime

class TestOfManager(TestCase):
    def tearDown(self):
        try:
            reversion.unregister(User)
        except:
            pass

    def test_get_for_object_reference_returns_appropriate_versions(self):
        user = User.objects.create(
            username='random-%d' % random.randint(1, 100),
            email='admin@admin.com',
        )
        random_number_of_versions = random.randint(1, 100)
        reversion.register(User)
        for i in range(random_number_of_versions):
            with reversion.revision:
                user.username = 'random-%d' % i
                user.save()
        versions = Version.objects.get_for_object_reference(User, user.pk)
        self.assertEqual(len(versions), random_number_of_versions)

    def test_get_for_object_returns_appropriate_versions(self):
        user = User.objects.create(
            username='random-%d' % random.randint(1, 100),
            email='admin@admin.com',
        )
        random_number_of_versions = random.randint(1, 100)
        reversion.register(User)
        for i in range(random_number_of_versions):
            with reversion.revision:
                user.username = 'random-%d' % i
                user.save()
        versions = Version.objects.get_for_object(user)
        self.assertEqual(len(versions), random_number_of_versions)

    def test_get_unique_for_object_returns_appropriate_versions(self):
        user = User.objects.create(
            username='random-%d' % random.randint(2, 100),
            email='admin@admin.com',
        )

        # make sure the random number is evenly divisible
        random_number_of_versions = abs(random.randint(2, 50) & (~0<<1)) 
        reversion.register(User)
        user = User.objects.get(email='admin@admin.com')
        for i in range(random_number_of_versions/2):
            with reversion.revision:
                user.username = 'sequential-%d' % i
                user.save()

        for i in range(random_number_of_versions/2, 0, -1):
            with reversion.revision:
                user.username = 'sequential-%d' % i
                user.save()

        versions = Version.objects.get_unique_for_object(user)
        self.assertEqual(len(versions), random_number_of_versions)

    def test_get_for_date_raises_does_not_exist_on_none_available(self):
        user = User.objects.create(
            username='rand-%d' % random.randint(1, 100),
        )
        reversion.register(User)
        self.assertRaises(Version.DoesNotExist, Version.objects.get_for_date, user, datetime.datetime.now()) 

    def test_get_for_date_returns_version_if_one_is_available(self):
        reversion.register(User)
        with reversion.revision:
            user = User.objects.create(
                username='rand-%d' % random.randint(1, 100),
            )
        now = datetime.datetime.now()
        version = Version.objects.get_for_date(user, now) 
        self.assertTrue(version.revision.date_created <= now) 

    def test_get_deleted_object_raises_does_not_exist_on_none_available(self):
        user = User.objects.create(
            username='rand-%d' % random.randint(1, 100),
        )
        pk = user.pk
        user.delete()
        reversion.register(User)
        self.assertRaises(Version.DoesNotExist, Version.objects.get_deleted_object, User, pk) 

    def test_get_deleted_object_returns_version_if_one_is_available(self):
        reversion.register(User)
        pk = None
        with reversion.revision:
            user = User.objects.create(
                username='rand-%d' % random.randint(1, 100),
            )
            pk = user.pk
        with reversion.revision:
            user.delete()
        version = Version.objects.get_deleted_object(User, pk)
        self.assertEqual(version.object_version.object.pk, pk) 

    def test_get_deleted_returns_appropriate_list_of_deleted_objects_for_model(self):
        reversion.register(User)
        random_number_of_users = random.randint(1, 100)
        for i in range(random_number_of_users):
            user = None
            with reversion.revision:
                user = User.objects.create(
                    username='sequential-%d' % i
                )
        with reversion.revision:
            User.objects.all().delete()

        deleted = Version.objects.get_deleted(User)
        self.assertEqual(len(deleted), random_number_of_users)

