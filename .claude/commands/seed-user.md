---
description: Create a single dummy user in the database
allowed-tools: Read, Bash(python3:*)
---

Read database/db.py to understand the users table schema and the get_db() helper.

Then write and run a Python script using Bash that:

1. Generates a realistic random Indian user using your own knowledge of common Indian names across regions:
   - Name: a realistic Indian first + last name
   - Email: derived from the name with a random 2-3 digit number suffix (e.g. rahul.sharma91@gmail.com)
   - Password: "password123" hashed with werkzeug's generate_password_hash
   - created_at: current datetime

2. Checks if the generated email already exists in the users table.
   - If it exists, generate a new email with a different number suffix and check again.

3. Inserts the user into the users table using the get_db() helper.
   - Use a parameterized query (no string formatting in SQL).
   - Commit the transaction and close the connection.

4. Prints a confirmation showing the new user's id, name, email and created_at.
   - Do NOT print the password hash.

Rules:
- Only insert one user.
- Do not modify the database schema or any existing rows.
- Do not create or edit any project files. Run the script inline with `python3 -c` or a heredoc.
- If anything fails, show the error and stop. Do not retry with schema changes.