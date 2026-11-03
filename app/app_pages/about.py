"""Public landing page. Holds no data, so it is safe to show anyone."""

import streamlit as st

import access

access.require('about')

st.title('Gowanus Canal water data')
st.markdown("""
The Gowanus Dredgers collect water-quality readings
on the Gowanus Canal in Brooklyn. This site brings their data together with
other public and partner sources to answer questions like *is it safe to swim
today?* and *how does rain change the water?*

**Sources**

- **Duro sonde** — the Dredgers' own field instrument: dissolved oxygen,
  temperature, salinity and more, logged on canal outings from August 2023
  to October 2024. The sonde is now out of service, so no new readings are
  coming in.
- **Citizens' Water Quality Testing (CWQT)** — weekly Enterococcus (bacteria)
  sampling, with SwimmableNYC and the Billion Oyster Project.
- **Gowanus Superfund turbidity monitoring** — 15-minute readings published
  with the EPA cleanup's weekly reports.
""")

if st.session_state.get('viewer_level', 'public') == 'public':
    st.info('The charts are shared with the project team for now. '
            'Sign in with Google from the sidebar if you have access.')
else:
    st.success('Pick a page from the sidebar to see the data.')
