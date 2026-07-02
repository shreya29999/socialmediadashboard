import unittest

from admin_utils import resolve_admin_for_signup


class ResolveAdminSignupTests(unittest.TestCase):
    def test_invite_code_takes_priority(self):
        admins = [
            {"id": 1, "email": "alpha@example.com", "role": "admin", "invite_code": "ALPHA"},
            {"id": 2, "email": "beta@example.com", "role": "admin", "invite_code": "BETA"},
        ]
        admin = resolve_admin_for_signup(
            email="newuser@acme.com",
            invite_code="BETA",
            admin_email=None,
            admins=admins,
            domain_mapping={"shilsha.com": "alpha@example.com"},
        )
        self.assertEqual(admin["email"], "beta@example.com")

    def test_domain_mapping_resolves_admin(self):
        admins = [
            {"id": 1, "email": "alpha@example.com", "role": "admin", "invite_code": "ALPHA"},
        ]
        admin = resolve_admin_for_signup(
            email="newuser@shilsha.com",
            invite_code=None,
            admin_email=None,
            admins=admins,
            domain_mapping={"shilsha.com": "alpha@example.com"},
        )
        self.assertEqual(admin["email"], "alpha@example.com")


if __name__ == "__main__":
    unittest.main()
