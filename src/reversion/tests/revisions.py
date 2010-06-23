from reversion import revisions
from django.test import TestCase
from django.contrib.auth.models import User
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



