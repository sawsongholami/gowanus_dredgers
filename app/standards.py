"""Water quality standards, kept in one place for the app and the static page.

Plain numbers, no imports, so dashboard/build_data.py can read this file
without pulling in Streamlit or the database.

Enterococcus, MPN per 100 mL: New York State's bathing-beach rules (10 NYCRR
Subpart 6-2), which NYC's health department also uses.
- SWIM_THRESHOLD_MPN: no single sample above 104.
- GEO_MEAN_STANDARD_MPN: the geometric mean of five or more samples taken
  within GEO_MEAN_WINDOW_DAYS must not exceed 35.
Single samples are judged against 104 only. Geometric means are rated on the
bands the Citizens' Water Quality Testing programme uses: good (35 or less),
advisory (up to 104), poor (over 104).

Dissolved oxygen: New York State's chronic standard for Class SD waters.
"""

SWIM_THRESHOLD_MPN = 104
GEO_MEAN_STANDARD_MPN = 35
GEO_MEAN_WINDOW_DAYS = 30
GEO_MEAN_MIN_SAMPLES = 5

DO_STANDARD_MG_L = 5.0
