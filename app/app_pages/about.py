"""Public landing page. Holds no data, so it is safe to show anyone.

The copy is adapted from the partners' draft "Dashboard / Website Copy" (a
tab of the SOW doc in the shared drive), trimmed to what this dashboard
shows. Where the draft and the data disagreed (dates, how often the sonde
went out, what updates), the data won.
"""

import streamlit as st

import access
import site_map

access.require('about')

st.title('Gowanus Dredgers Data Dashboard')
st.markdown("""
The Gowanus Canal is a federal Superfund site whose water quality changes
hour to hour: tides, rain-triggered sewage overflows, wind, and temperature
all move it. This data dashboard, built by the Gowanus Dredgers Canoe Club
in partnership with Urban Data Response, provides a historical lens on the
health of the canal over time.
""")

if st.session_state.get('viewer_level', 'public') == 'public':
    st.info('The charts are shared with the project team for now. '
            'Sign in with Google from the sidebar if you have access.')

st.header('How to use this dashboard')
st.markdown("""
This dashboard is historical, not real-time. It brings together bacteria
results, water quality readings, turbidity monitoring, weather and tides, so
you can see how they moved together over time. Each page starts from a
question:

- **Is the canal safe to swim in?** Weekly Enterococcus bacteria counts
  since 2012, year by year, and what rain and tide do to them.
- **Can fish survive in the canal?** Dissolved oxygen, site by site.
- **How much does dredging cloud the water?** Turbidity through the two
  phases of the cleanup so far.
- **Explore the data.** Pick any of the datasets and put them side by side.

Under each chart, a map shows where its data was collected. Bacteria,
turbidity and weather are refreshed daily as their sources publish; the
Dredgers' own water quality readings are a closed record, August 2023 to
October 2024.

*What is Enterococcus?* It's a bacterium that lives in the human gut, so
it's commonly used as a sign of poop in the water!
[Learn more at epa.gov »](https://www.epa.gov/national-aquatic-resource-surveys/indicators-enterococci)
""")

st.header('History of the Gowanus Canal')
st.markdown("""
The Gowanus Dredgers Canoe Club formed in 1999, when the canal was in rough
shape: industrial pollution, illegal dumping, and raw sewage from combined
sewer overflow (CSO) outfalls. The canal itself is about two miles long,
running from its upper end near Butler Street down to the harbor. It's
tidal, with as much as a six-foot swing between high and low tide, so the
water moving through it is never static.
""")
site_map.show({'Monitoring sites': list(site_map.SITES)}, label='Map: the canal and its monitoring sites',
              expanded=True)
st.markdown("""
The neighborhood around the canal is changing just as fast as the water. It
was designated a Superfund site in 2010, but cleanup hadn't started even as
rezoning began bringing new residential buildings to the waterfront.
Dredging of contaminated sediment and construction of new sewage retention
infrastructure are now underway at the same time thousands of new apartments
are being built nearby. The key question for the canal now is whether
conditions are improving, holding steady, or facing new risks as more people
move in before the infrastructure catches up.
""")

st.header('Why is this important')
st.markdown("""
Gowanus is served by a combined sewer system, which carries stormwater and
sewage in the same pipes. During heavy rain, the system overflows directly
into the canal rather than backing up into streets and basements. That's
the source of most of the canal's roughly 363 million gallons of combined
sewer overflow each year.

The pressure on that system keeps growing. More than 8,000 new apartments
are planned or under construction in the rezoned neighborhood around the
canal, meaning thousands more toilets connected to the same combined sewers,
arriving well before the new tanks are finished.

NYC DEP is building two underground storage tanks to hold that overflow
instead: an 8-million-gallon tank at the Red Hook (Head End) site and a
smaller tank at Owls Head, with 1.6 and 2 acres of new public open space
planned above them. Excavation is complete at both sites and construction is
underway on the tank structures. Completion dates have shifted more than
once as the project has moved forward; as of 2026, city and federal
materials point to the tanks coming online on different schedules between
2027 and the early 2030s.

The EPA has been direct about why this matters for the larger Superfund
cleanup: dredging and capping the canal bottom only holds up if the water
isn't recontaminated afterward. Without the tanks running, stormwater will
keep carrying sewage and sediment back into a canal the EPA has spent years
remediating.

There's already a small-scale preview of what a fix can look like. A
flushing tunnel connects the canal to Buttermilk Channel near Governors
Island, and in August 2024 volunteer data captured dissolved oxygen jumping
within about a day of the tunnel being switched back on, after weeks of
near-zero readings at two sites. It's a small example of an engineering fix
showing up almost immediately in the data. The CSO tanks are a far bigger
intervention, and ongoing monitoring is how the neighborhood will know
whether they deliver a similar result.

Official monitoring of the canal is sparse to begin with. The EPA and NYC
DEP have historically sampled only a few times a month, and the city stopped
publicly sharing its own monitoring data in 2022. The tools that do exist
fall short in their own ways: the Hudson River Environmental Conditions
Observing System has no monitors in the Gowanus Canal itself; the Gowanus
Remediation Team's buoys collect data continuously but report it only
sporadically, track just turbidity, and publish it as images inside PDFs;
and NYC's Open Data portal lists canal monitoring sites where the most
recent upload is often more than a year old. None of that adds up to a
local, frequent, current picture, which is exactly why volunteer data has
mattered here, and why consistent monitoring needs to continue.

That makes this a rare, time-limited opportunity. Once the tanks come
online, the frequency and severity of CSO events in the canal should
measurably drop, if they perform as designed. Proving that takes monitoring
data from before and after, collected the same way, at the same sites, for
long enough to see a real pattern. This dashboard's historical record of
weather, water quality, and Enterococcus data is meant to be that "before"
baseline. What's needed next is funding to keep collecting comparable data
once the tanks are running, so the neighborhood, not just DEP, can see
whether the investment worked.
""")

st.header('What does the data mean')
st.markdown("""
**Water quality (Duro Field Sonde).** Volunteers carried a handheld sensor
to sites along the canal and logged readings at each stop. The dashboard
shows three of its measurements:

| Measurement | What it means | Unit | Why it matters |
|---|---|---|---|
| Dissolved oxygen | Oxygen available to aquatic life | mg/L | Below 5 mg/L stresses fish, below 3 mg/L can't support them, below 1 mg/L is hypoxic |
| Water temperature | Temperature of the canal water | °C | Warmer water holds less oxygen; the 2023 fish kill happened during a heat wave |
| Salinity | Salt content | ppt | Drops sharply during rain and CSO events, as stormwater and sewage dilute the canal's brackish water |

**Enterococcus.** A gut bacterium found in sewage. Its presence in canal
water is one of the clearest signs that raw sewage has reached the canal,
most often through a combined sewer overflow. It is measured in MPN (most
probable number) of colonies per 100 mL of water.

**Turbidity.** How cloudy the water is, measured by the Superfund cleanup's
buoys while dredging stirs up the canal floor.

**Weather and tides.** Rainfall drives most of what happens in the canal,
since even a modest storm can trigger a combined sewer overflow. The
dashboard pairs rain with the readings above so you can look for cause and
effect: a rain event, a drop in salinity, a spike in Enterococcus, and a dip
in dissolved oxygen that can take hours or days to recover.
""")

st.header('How this data was collected')
st.markdown("""
Water quality readings came from a Duro UAS Field Sonde, carried along the
canal by the club's captain on 210 outings between August 2023 and October
2024, most often to Douglass Street, Second Street, the Fourth Street
Turning Basin and the Ninth Street Bridge. In the water, the sonde logged a
reading about every 30 seconds.

**The Duro sonde is no longer functioning, and water quality readings are
no longer being collected.** The last outing on record is October 18, 2024.
The water quality data in this dashboard is a closed historical record, not
an ongoing feed. Replacing the instrument, and funding its regular use, is
one of the clearest near-term needs this project is meant to make visible.

Enterococcus samples were collected separately, through Citizens' Water
Quality Testing, a regional community science network (SwimmableNYC and the
Billion Oyster Project) that samples spring through fall; the Dredgers
extended their own testing over the winter of 2023-24 to see what off-season
conditions looked like.

Turbidity comes from the 15-minute buoy readings published with the Gowanus
Superfund cleanup's weekly reports. Rainfall next to the bacteria samples is
the Central Park gauge figure the testing network records; day-by-day
weather is from Open-Meteo, a weather model; tides are NOAA's predictions
for Gowanus Bay.
""")

st.header('About the Gowanus Dredgers')
st.markdown("""
The Gowanus Dredgers Canoe Club is an all-volunteer nonprofit that has
worked since 1999 to open up the Gowanus waterfront through recreation,
education, and advocacy. Canoeing is the club's core activity: members and
the public take canoes out on the canal through free walk-up events, guided
tours, and outings from the club's boathouses on Second Street and 19th
Street.

Paddle with the Dredgers or ask about joining a testing outing:
[gowanusdredgers.org](https://gowanusdredgers.org/)
""")
