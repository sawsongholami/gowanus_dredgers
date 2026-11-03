"""
Manages who can see the Streamlit app's private pages (the `app_viewers`
table; the rules are in app/access.py).

Usage:
    python viewers.py list
    python viewers.py add someone@gmail.com team "Dredgers board"
    python viewers.py add someone@gmail.com admin      # also sees the viewer list
    python viewers.py remove someone@gmail.com

Use the email of the Google account they will sign in with. Adding an
existing email updates its role and note. Changes reach the app within a
minute.
"""

import argparse

from sqlalchemy import text

import apply_schema
import write_to_db

ROLES = ('team', 'admin')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='show everyone with access')
    add = sub.add_parser('add', help='give someone access, or change their role')
    add.add_argument('email')
    add.add_argument('role', choices=ROLES)
    add.add_argument('note', nargs='?', default=None, help='who they are / why they have access')
    remove = sub.add_parser('remove', help="take someone's access away")
    remove.add_argument('email')
    args = parser.parse_args()

    apply_schema.apply()
    engine = write_to_db.get_engine()
    with engine.begin() as conn:
        if args.command == 'add':
            conn.execute(text("""
                INSERT INTO app_viewers (email, role, note) VALUES (:email, :role, :note)
                ON CONFLICT (email) DO UPDATE SET role = EXCLUDED.role,
                                                  note = COALESCE(EXCLUDED.note, app_viewers.note)
            """), {'email': args.email.strip().lower(), 'role': args.role, 'note': args.note})
            print(f'{args.email.strip().lower()} can now see the app as {args.role}.')
        elif args.command == 'remove':
            result = conn.execute(text('DELETE FROM app_viewers WHERE email = :email'),
                                  {'email': args.email.strip().lower()})
            print('Removed.' if result.rowcount else 'That email was not on the list.')
        rows = conn.execute(text('SELECT email, role, note FROM app_viewers ORDER BY role, email')).fetchall()

    print(f'\n{len(rows)} viewer(s):')
    for email, role, note in rows:
        print(f'  {role:<6} {email}' + (f'  ({note})' if note else ''))


if __name__ == '__main__':
    main()
