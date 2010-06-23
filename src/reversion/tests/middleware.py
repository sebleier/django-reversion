from django.contrib.auth.models import User, AnonymousUser
from django.test import TestCase
from reversion.middleware import RevisionMiddleware
import reversion
import random

class TestOfRevisionMiddleware(TestCase):
    def tearDown(self):
        while reversion.revision.is_active():
            reversion.revision.end()

    def test_process_request_attaches_user_if_authenticated(self):
        middleware = RevisionMiddleware()
        user = User.objects.create(
            username='rand-%d' % random.randint(1, 100)
        )
        fake_request = type('FakeRequest', (object,), {'user':user})()
        middleware.process_request(fake_request)
        self.assertEqual(reversion.revision._state.depth, 1)
        self.assertEqual(user.pk, reversion.revision.user.pk)

    def test_process_request_does_not_attach_user_if_not_authenticated(self):
        middleware = RevisionMiddleware()
        user = AnonymousUser()
        fake_request = type('FakeRequest', (object,), {'user':user})()
        middleware.process_request(fake_request)
        self.assertEqual(reversion.revision._state.depth, 1)
        self.assertEqual(reversion.revision.user, None)

    def test_process_response_leaves_revision_in_empty_state(self):
        anything, anything_else = random.randint(1, 100), random.randint(1, 100)
        middleware = RevisionMiddleware()
        random_number_of_starts = random.randint(1, 100)
        for i in range(random_number_of_starts):
            reversion.revision.start()

        middleware.process_response(anything, anything_else)
        self.assertEqual(reversion.revision._state.depth, 0)
    
    def test_process_exception_invalidates_revision(self):
        anything, anything_else = random.randint(1, 100), random.randint(1, 100)
        middleware = RevisionMiddleware()
        random_number_of_starts = random.randint(1, 100)
        for i in range(random_number_of_starts):
            reversion.revision.start()

        middleware.process_exception(anything, anything_else)
        self.assertTrue(reversion.revision._state.is_invalid)
