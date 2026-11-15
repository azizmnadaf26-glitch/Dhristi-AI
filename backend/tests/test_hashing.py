from app.security.hashing import hash_password, verify_password


def test_hash_and_verify():
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password", hashed)


def test_same_password_gives_different_hashes():
    # Each hash includes a random "salt", so two hashes of the same password differ.
    assert hash_password("same-password-1") != hash_password("same-password-1")