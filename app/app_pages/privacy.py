"""Public privacy policy. Google's sign-in setup requires a link to one. Holds no data."""

import streamlit as st

import access

access.require('privacy')

st.title('Privacy')
st.markdown("""
This site belongs to the Gowanus Dredgers' volunteer water-data project.

**What we collect.** Signing in is optional and only needed to see the
team pages. When you sign in with Google, the site receives your name and
email address from Google. It uses your email for one thing: checking
whether it is on the list of people allowed to see the team pages. Nothing
about your visit is stored, and the site sets only the sign-in cookie that
keeps you signed in (for up to 30 days, or until you sign out).

**Who is on the viewer list.** The list holds the email address, a role
and a short note for each person the project team has given access. It is
kept in the project's database and used only to decide what each viewer
can see. To be removed from it, ask the project team.

**Maps.** The street map behind each map on this site is loaded by your
browser from CARTO, a map provider, which sees the request the way any
website you visit does. We don't send it anything about you.

**What we don't do.** We don't sell, share or analyse your information,
send email, or use it for anything other than access to this site.

**Data sources.** The water-quality data shown here comes from the Gowanus
Dredgers' own measurements and from partner and public sources, credited on
each page.
""")
