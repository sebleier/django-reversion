from reversion import revisions
from django.test import TestCase
from django.contrib.auth.models import User, Group
import random
import datetime

class TestOfRegistrationInfo(TestCase):
    def test_of_init(self):
        fields, file_fields, follow, format = (
            random.randint(1, 100) for i in range(4)
        )
        info = revisions.RegistrationInfo(fields, file_fields, follow, format)
        self.assertEqual(info.fields, fields)
        self.assertEqual(info.file_fields, file_fields)
        self.assertEqual(info.follow, follow)
        self.assertEqual(info.format, format)

class TestOfRevisionState(TestCase):
    def test_of_init(self):
        state = revisions.RevisionState()
        self.assertEqual(state.objects, set())
        self.assertEqual(state.user, None)
        self.assertEqual(state.comment, "")
        self.assertEqual(state.depth, 0)
        self.assertEqual(state.is_invalid, False)
        self.assertEqual(state.meta, [])

    def test_of_clear(self):
        state = revisions.RevisionState()
        for i in ('objects', 'user', 'comment', 'depth', 'is_invalid', 'meta'):
            setattr(state, i, random.randint(1, 100))
            state.clear() 
            self.assertEqual(state.objects, set())
            self.assertEqual(state.user, None)
            self.assertEqual(state.comment, "")
            self.assertEqual(state.depth, 0)
            self.assertEqual(state.is_invalid, False)
            self.assertEqual(state.meta, [])

class TestOfRevisionManager(TestCase):
    def test_of_init(self):
        manager = revisions.RevisionManager()
        self.assertEqual(manager._registry, {})
        self.assertTrue(isinstance(manager._state, revisions.RevisionState))

    def test_reregister_raises_registration_error(self):
        manager = revisions.RevisionManager()
        manager.register(User)
        self.assertRaises(revisions.RegistrationError, manager.register, User)
        
    def test_proxy_model_register_raises_registration_error_if_parent_is_not_registered(self):
        class AbUser(User):
            class Meta:
                proxy = True
        manager = revisions.RevisionManager()
        self.assertRaises(revisions.RegistrationError, manager.register, AbUser)

    def test_empty_fields_results_in_all_fields_being_watched(self):
        manager = revisions.RevisionManager()
        user_opts = User._meta
        local_fields = user_opts.local_fields + user_opts.local_many_to_many
        local_field_names = tuple([f.name for f in local_fields])
        manager.register(User)
        info = manager.get_registration_info(User)
        self.assertEqual(local_field_names, info.fields)

    def test_fields_get_added_to_info_and_arent_validated(self):
        manager = revisions.RevisionManager()
        user_opts = User._meta
        fields = tuple(['random-%d' % random.randint(1, 100) for i in range(0, random.randint(1,10))])
        manager.register(User, fields)
        info = manager.get_registration_info(User)
        self.assertEqual(fields, info.fields)
        
    def test_is_registered(self):
        manager = revisions.RevisionManager()
        self.assertFalse(manager.is_registered(User))
        manager.register(User)
        self.assertTrue(manager.is_registered(User))

    def test_post_save_connect_is_triggered(self):
        old_post_save = revisions.post_save
        try:
            manager = revisions.RevisionManager()
            class NewPostSave(object):
                def __init__(_self):
                    _self.connect_args = []

                def connect(_self, *args):
                    _self.connect_args = args
            revisions.post_save = NewPostSave()
            manager.register(User)
            self.assertTrue(manager.post_save_receiver in revisions.post_save.connect_args)
            self.assertTrue(User in revisions.post_save.connect_args)
        finally:
            revisions.post_save = old_post_save

    def test_get_registration_info_throws_registration_error_on_unregistered_classes(self):
        manager = revisions.RevisionManager()
        self.assertRaises(revisions.RegistrationError, manager.get_registration_info, User)

    def test_get_registration_returns_info_if_model_is_registered(self):
        manager = revisions.RevisionManager()
        manager.register(User)
        self.assertTrue(isinstance(manager.get_registration_info(User), revisions.RegistrationInfo))

    def test_unregister_throws_registration_error_on_non_registered_model(self):
        manager = revisions.RevisionManager()
        self.assertRaises(revisions.RegistrationError, manager.unregister, User)

    def test_unregister_triggers_post_save_disconnect(self):
        old_post_save = revisions.post_save
        try:
            manager = revisions.RevisionManager()
            class NewPostSave(object):
                def __init__(_self):
                    _self.connect_args = []
                    _self.disconnect_args = []

                def connect(_self, *args):
                    _self.connect_args = args

                def disconnect(_self, *args):
                    _self.disconnect_args = args

            revisions.post_save = NewPostSave()
            manager.register(User)
            manager.unregister(User)
            self.assertTrue(manager.post_save_receiver in revisions.post_save.connect_args)
            self.assertTrue(User in revisions.post_save.connect_args)
            self.assertEqual(revisions.post_save.connect_args, revisions.post_save.disconnect_args)
        finally:
            revisions.post_save = old_post_save

    def test_functions_throw_revisionmanagementerror_on_inactive_manager(self):
        manager = revisions.RevisionManager()
        self.assertRaises(revisions.RevisionManagementError, manager.add, random.randint(1, 100))

        self.assertRaises(revisions.RevisionManagementError, manager.set_user, random.randint(1, 100))
        self.assertRaises(revisions.RevisionManagementError, manager.get_user)

        self.assertRaises(revisions.RevisionManagementError, manager.set_comment, random.randint(1, 100))
        self.assertRaises(revisions.RevisionManagementError, manager.get_comment)
        
        self.assertRaises(revisions.RevisionManagementError, manager.add_meta, User, **{'rand_%d'%random.randint(1,100):random.randint(1,100)})

        self.assertRaises(revisions.RevisionManagementError, manager.invalidate)

        self.assertRaises(revisions.RevisionManagementError, manager.end)

    def test_invalidate(self):
        manager = revisions.RevisionManager()
        manager.start()
        self.assertFalse(manager.is_invalid())
        manager.invalidate()
        self.assertTrue(manager.is_invalid())
        manager.end()

    def test_end_isnt_triggered_until_stack_fully_popped(self):
        manager = revisions.RevisionManager()
        manager.register(User)
        manager.start()
        manager.start()
        User.objects.create(username='rand%d'%random.randint(1,100))
        manager.end()
        self.assertEqual(len(revisions.Version.objects.all()), 0)

    def test_end_triggers_versioning_when_stack_is_empty(self):
        manager = revisions.RevisionManager()
        manager.register(User)
        manager.start()
        User.objects.create(username='rand%d'%random.randint(1,100))
        manager.end()
        self.assertEqual(len(revisions.Version.objects.all()), 1)

    def test_follow_relationships_follows_m2m_relationships(self):
        manager = revisions.RevisionManager()
        manager.register(User, follow=('groups',))
        manager.register(Group)
        user = User.objects.create(username='rand%d'%random.randint(1, 100))
        random_group_membership = random.randint(1, 100)
        groups = [user.groups.create(
            name='rand%d'%i
        ) for i in range(random_group_membership)]
        results = manager.follow_relationships(set([user]))

        # add 1 to represent the User
        self.assertEqual(len(results), random_group_membership + 1)
        for group in groups:
            self.assertTrue(group in results)
        self.assertTrue(user in results)

    def test_follow_relationships_follows_proxy_relationships(self):
        manager = revisions.RevisionManager()
        manager.register(User, follow=('groups',))
        manager.register(Group)
        class AbUser(User):
            class Meta:
                proxy = True
        manager.register(AbUser)
        user = AbUser.objects.create(username='rand%d'%random.randint(1, 100))
        random_group_membership = random.randint(1, 100)
        groups = [user.groups.create(
            name='rand%d'%i
        ) for i in range(random_group_membership)]
        results = manager.follow_relationships(set([user]))

        # add 2, 1 for the AbUser entry, and one for the User parent of that AbUser
        self.assertEqual(len(results), random_group_membership + 2)
        for group in groups:
            self.assertTrue(group in results)
        self.assertTrue(user in results)

    def test_follow_relationships_raises_registrationerror_if_followed_group_isnt_registered(self):
        manager = revisions.RevisionManager()
        manager.register(User, follow=('groups',))
        user = User.objects.create(username='rand%d'%random.randint(1, 100))
        random_group_membership = random.randint(1, 100)
        groups = [user.groups.create(
            name='rand%d'%i
        ) for i in range(random_group_membership)]
        self.assertRaises(revisions.RegistrationError, manager.follow_relationships, set([user]))
        user.groups.all().delete()

        # THIS IS A HUGE GOTCHA:
        #   if it doesn't run into any of the non-registered items, it DOESN'T ERROR OUT
        #   bad, bad, BAD
        self.assertEqual(manager.follow_relationships(set([user])), set([user]))

    def test_follow_relationships_raises_a_typeerror_on_non_related_follow_fields(self):
        manager = revisions.RevisionManager()
        user_methods = [i for i in dir(User) if isinstance(getattr(User, i), type(User.get_profile))]
        user_method = user_methods[random.randint(0,len(user_methods)-1)]

        manager.register(User, follow=(user_method,))
        user = User.objects.create(username='rand%d'%random.randint(1, 100))
        self.assertRaises(TypeError, manager.follow_relationships, set([user]))

    def test_follow_relationships_returns_only_distinct_objects(self):
        manager = revisions.RevisionManager()
        manager.register(User, follow=('groups',))
        manager.register(Group)
        user = User.objects.create(username='rand%d'%random.randint(1, 100))
        user2 = User.objects.create(username='rand%d-2'%random.randint(1, 100))
        random_group_membership = random.randint(1, 100)
        groups = [user.groups.create(
            name='rand%d'%i
        ) for i in range(random_group_membership)]
        [user2.groups.add(group) for group in groups]
        results = manager.follow_relationships(set([user, user2]))

        # add 1 to represent the User
        self.assertEqual(len(results), random_group_membership + 2)
        for group in groups:
            self.assertTrue(group in results)
        self.assertTrue(user in results)
        self.assertTrue(user2 in results)
