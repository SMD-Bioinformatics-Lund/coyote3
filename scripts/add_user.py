#!/usr/bin/env python3

#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

import os

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash


def main():
    # Connect to the DB
    """Handle main.

    Returns:
        The function result.
    """
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:5818/coyote3")
    db_name = os.getenv("COYOTE3_DB", "coyote3")
    collection = MongoClient(mongo_uri)[db_name]["users"]

    # Ask for data to store
    user = input("Enter your username: ").strip().lower()
    email = input("Enter email (optional): ").strip().lower()
    password = input("Enter your password: ")
    grp_string = input("Enter assays/groups (comma separated, optional): ").strip()
    role = input("Enter role (default: viewer): ").strip().lower() or "viewer"
    pass_hash = generate_password_hash(password, method="pbkdf2:sha256")

    grp_arr = [g.strip() for g in grp_string.split(",") if g.strip()]

    # Insert the user in the DB
    try:
        collection.insert_one(
            {
                "username": user,
                "email": email,
                "password": pass_hash,
                "assays": grp_arr,
                "role": role,
                "is_active": True,
                "auth_type": "coyote3",
            }
        )
        print("User created.")
    except DuplicateKeyError:
        print("User already present in DB.")


if __name__ == "__main__":
    main()
