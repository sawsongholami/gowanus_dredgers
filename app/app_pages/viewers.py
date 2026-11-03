"""Admin only: the current viewer list. Changes go through data_import/viewers.py."""

import streamlit as st

import access
import data

access.require('viewers')

st.title('Who can see this')
st.dataframe(data.viewers(), hide_index=True)
st.markdown("""
To add, change or remove someone, run from the repo root (it uses the owner
login in `.env`, not the app's read-only one):

```bash
python data_import/viewers.py add someone@gmail.com team "what they're for"
python data_import/viewers.py remove someone@gmail.com
```

`team` sees every chart; `admin` also sees this page. A change reaches the
app within a minute.
""")
