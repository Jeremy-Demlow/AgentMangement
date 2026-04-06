"""Snowflake connection helper.

Provides a connection factory that reads from environment config
and supports both interactive (externalbrowser) and CI (key-pair) auth.

Implements REQ-001: Environment Configuration System.
"""
from __future__ import annotations

import os
from typing import Any

import snowflake.connector


def connect(config: dict, **overrides: Any) -> snowflake.connector.SnowflakeConnection:
    sf = config["snowflake"]
    deploy = config["deployment"]

    if os.environ.get("SNOWFLAKE_CONNECTION_NAME"):
        conn_params: dict[str, Any] = {
            "connection_name": os.environ["SNOWFLAKE_CONNECTION_NAME"],
            "role": sf["role"],
            "warehouse": sf["warehouse"],
            "database": deploy["database"],
        }
        conn_params.update(overrides)
        return snowflake.connector.connect(**conn_params)

    params: dict[str, Any] = {
        "account": sf.get("account", os.environ.get("SNOWFLAKE_ACCOUNT", "")),
        "user": sf.get("user", os.environ.get("SNOWFLAKE_USER", "")),
        "role": sf["role"],
        "warehouse": sf["warehouse"],
        "database": deploy["database"],
    }

    if os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"):
        from cryptography.hazmat.primitives import serialization
        from pathlib import Path
        key_path = Path(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]).expanduser()
        passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
        with open(key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=passphrase.encode() if passphrase else None,
            )
        params["private_key"] = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    elif os.environ.get("SNOWFLAKE_PASSWORD"):
        params["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    else:
        params["authenticator"] = sf.get("authenticator", "externalbrowser")

    params.update(overrides)
    return snowflake.connector.connect(**params)
