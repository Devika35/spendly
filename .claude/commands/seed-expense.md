---
description: Seed realistic dummy expenses for a specific user
argument-hint: "<user_id> <count> <months>"
allowed-tools: Read, Bash(python3:*)
---

Read database/db.py to understand the expenses table schema, the db connection pattern, and the database file name.

User input: $ARGUMENTS

## Step 1 — Parse arguments

Extract from $ARGUMENTS:
- user_id — integer
- count — integer, number of expenses to create
- months — integer, how many past months to spread them across

If any argument is missing or not a valid integer, stop and say:
"Usage: /seed-expense <user_id> <count> <months>
Example: /seed-expense 1 50 6"

## Step 2 — Validate the user

Write and run a Python script using Bash that checks whether a user with this user_id exists in the users table.

If the user does not exist, stop and say:
"No user found with id <user_id>. Run /seed-user first."

## Step 3 — Generate and insert expenses

In the same or a new Python script:

1. Generate `count` realistic Indian expenses:
   - category: one of Food, Transport, Bills, Shopping, Health, Entertainment, Education, Other
   - amount: realistic INR values for the category, for example:
     - Food: 50–800 (e.g. "Swiggy order", "Chai and samosa")
     - Transport: 20–500 (e.g. "Ola ride", "Metro card recharge")
     - Bills: 200–3000 (e.g. "Electricity bill", "Jio recharge")
     - Shopping: 200–5000 (e.g. "Myntra order", "Groceries at DMart")
     - Health: 100–2000 (e.g. "Pharmacy", "Doctor consultation")
     - Entertainment: 100–1500 (e.g. "Movie tickets", "Netflix subscription")
     - Education: 200–5000 (e.g. "Udemy course", "Books")
     - Other: 50–1000
   - description: a short, realistic description matching the category
   - date: a random date spread across the last `months` months, never in the future
   - Use the exact column names from the expenses table schema.

2. Insert all expenses for the given user_id in a single transaction, using parameterized queries (no string formatting in SQL).

3. If anything fails, roll back the transaction so no partial data is saved.

## Step 4 — Confirm

After inserting, print:
- Total number of expenses inserted
- Date range covered (earliest to latest date)
- Total amount spent (in ₹)
- A breakdown table by category: count and total amount

## Rules
- Do not modify the database schema or any existing rows.
- Do not create or edit any project files. Run Python inline with `python3 -c` or a heredoc.
- If anything fails, show the error and stop.