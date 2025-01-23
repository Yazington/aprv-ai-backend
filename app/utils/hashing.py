import hashlib


def hash_file_bytes(byte_content):
    """
    Compute SHA256 hash from a bytes object.

    :param byte_content: Content of the file in bytes.
    :return: SHA256 hash of the content.
    """
    sha256_hash = hashlib.sha256()
    sha256_hash.update(byte_content)  # Update hash with all bytes at once
    return sha256_hash.hexdigest()
