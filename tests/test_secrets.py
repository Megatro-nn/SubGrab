# SubGrab - downloads and fixes subtitles for your videos
# Copyright (C) 2026 Megatro-nn
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Secure secret storage: keyring when available, config.json fallback, one-time migration."""
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

import subgrab_core as C


class FakeKeyring:
    def __init__(self):
        self.store = {}

    def get_keyring(self):
        return self

    def get_password(self, service, name):
        return self.store.get((service, name))

    def set_password(self, service, name, value):
        self.store[(service, name)] = value

    def delete_password(self, service, name):
        del self.store[(service, name)]


class BrokenKeyring(FakeKeyring):
    def set_password(self, service, name, value):
        raise RuntimeError("backend unavailable")

    def get_password(self, service, name):
        raise RuntimeError("backend unavailable")


class SecretTests(unittest.TestCase):
    def setUp(self):
        self.old = C._keyring
        C._keyring = FakeKeyring()

    def tearDown(self):
        C._keyring = self.old

    def test_set_secret_uses_keyring_and_scrubs_config(self):
        cfg = {"subsource_key": "plain"}
        where = C.set_secret(cfg, "subsource_key", "abc")
        self.assertEqual(where, "keyring")
        self.assertNotIn("subsource_key", cfg)
        self.assertEqual(C._keyring.get_password(C.KEYRING_SERVICE, "subsource_key"), "abc")

    def test_get_secret_prefers_keyring(self):
        C._keyring.set_password(C.KEYRING_SERVICE, "os_key", "from-ring")
        self.assertEqual(C.get_secret({"os_key": "from-config"}, "os_key"), "from-ring")
        self.assertEqual(C.get_secret({"os_key": "from-config"}, "missing", "d"), "d")

    def test_migrate_moves_plaintext_and_clears_it(self):
        cfg = {"subsource_key": "k1", "os_key": "k2", "os_pass": "p", "os_user": "u"}
        self.assertTrue(C.migrate_secrets(cfg))
        self.assertFalse(any(k in cfg for k in C.SECRET_KEYS))
        self.assertEqual(cfg["os_user"], "u")  # usernames are not secrets
        self.assertFalse(C.migrate_secrets(cfg))  # nothing left to move

    def test_build_sources_reads_keyring(self):
        C._keyring.set_password(C.KEYRING_SERVICE, "subsource_key", "ss")
        C._keyring.set_password(C.KEYRING_SERVICE, "os_key", "ok")
        C._keyring.set_password(C.KEYRING_SERVICE, "os_pass", "op")
        src = C.build_sources({"os_user": "me"})
        self.assertEqual(src["SubSource"].key, "ss")
        self.assertEqual(src["OpenSubtitles"].key, "ok")
        self.assertEqual(src["OpenSubtitles"].user, "me")
        self.assertEqual(src["OpenSubtitles"].pw, "op")

    def test_backend_detection(self):
        self.assertEqual(C.secrets_backend(), "keyring")
        C._keyring = None
        self.assertEqual(C.secrets_backend(), "config")

    def test_fallback_to_config_when_no_keyring(self):
        C._keyring = None
        cfg = {}
        where = C.set_secret(cfg, "os_pass", "pw")
        self.assertEqual(where, "config")
        self.assertEqual(cfg["os_pass"], "pw")
        self.assertEqual(C.get_secret(cfg, "os_pass"), "pw")
        self.assertFalse(C.migrate_secrets(cfg))

    def test_broken_backend_falls_back_to_config(self):
        C._keyring = BrokenKeyring()
        cfg = {}
        where = C.set_secret(cfg, "os_pass", "pw")
        self.assertEqual(where, "config")
        self.assertEqual(cfg["os_pass"], "pw")

    def test_delete_clears_both_stores(self):
        cfg = {"os_key": "plain"}
        C._keyring.set_password(C.KEYRING_SERVICE, "os_key", "ring")
        C.set_secret(cfg, "os_key", "")
        self.assertNotIn("os_key", cfg)
        self.assertEqual(C.get_secret(cfg, "os_key"), "")


if __name__ == "__main__":
    unittest.main()
