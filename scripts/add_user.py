#!/usr/bin/python

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

from werkzeug.security import generate_password_hash
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError


def main():
    # Connect to the DB
    collection = MongoClient("dev-cdm-mongo:27017")["coyote"]["users"]

    # Ask for data to store
    user = input("Enter your username: ")
    password = input("Enter your password: ")
    grp_string = input("Enter groups: ")
    pass_hash = generate_password_hash(password, method="pbkdf2:sha256")

    grp_arr = grp_string.split(",")

    # Insert the user in the DB
    try:
        collection.insert(
            {"_id": user, "password": pass_hash, "groups": grp_arr}
        )
        print("User created.")
    except DuplicateKeyError:
        print("User already present in DB.")


if __name__ == "__main__":
    main()
