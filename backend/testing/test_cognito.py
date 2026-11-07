"""Verify client compatibility and JWT rejection without contacting Cognito."""

import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt

from src.auth import cognito


class CognitoTokenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_key = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        cls.public_key = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def setUp(self):
        for name, value in {
            'COGNITO_CLIENT_ID': 'legacy-client',
            'COGNITO_WEB_CLIENT_ID': 'web-client',
            'COGNITO_ISSUER': 'https://example.test/pool',
        }.items():
            patcher = patch.object(cognito, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(cognito, 'get_cognito_public_keys', return_value={'test': self.public_key})
        patcher.start()
        self.addCleanup(patcher.stop)

    def token(self, **overrides):
        claims = {
            'aud': 'web-client', 'iss': cognito.COGNITO_ISSUER,
            'exp': int(time.time()) + 300, 'token_use': 'id',
            'email': 'artist@example.test',
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private_key, algorithm='RS256', headers={'kid': 'test'})

    def test_accepts_web_and_legacy_clients(self):
        for audience in ('web-client', 'legacy-client'):
            with self.subTest(audience=audience):
                self.assertEqual(cognito.extract_user_from_token(self.token(aud=audience)), 'artist@example.test')

    def test_rejects_unconfigured_or_missing_audience(self):
        for audience in ('other-client', None, ['web-client'], ''):
            with self.subTest(audience=audience):
                self.assertIsNone(cognito.validate_token(self.token(aud=audience)))

    def test_rejects_invalid_claims(self):
        for overrides in ({'iss': 'https://other.test/pool'}, {'exp': 1}, {'token_use': 'access'}):
            with self.subTest(overrides=overrides):
                self.assertIsNone(cognito.validate_token(self.token(**overrides)))

    def test_rejects_invalid_signature(self):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with patch.object(cognito, 'get_cognito_public_keys', return_value={
            'test': other_key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
        }):
            self.assertIsNone(cognito.validate_token(self.token()))

    def test_legacy_only_configuration_does_not_allow_web_tokens(self):
        with patch.object(cognito, 'COGNITO_WEB_CLIENT_ID', None):
            self.assertIsNotNone(cognito.validate_token(self.token(aud='legacy-client')))
            self.assertIsNone(cognito.validate_token(self.token()))


if __name__ == '__main__':
    unittest.main()
