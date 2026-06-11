import pandas as pd
import pathlib as pl
import requests

dir_this_data = pl.Path(__file__).parent.parent.absolute() / 'data' / 'noaa'
dir_this_data.mkdir(exist_ok=True)

# PARAMETERS
begin_date = '20260101'  # Dates in YYYYMMDD
end_date = '20260131'

if __name__ == '__main__':
    url = 'https://api.tidesandcurrents.noaa.gov/api/prod/datagetter'

    params = {
        'product': 'predictions',
        'application': 'my_app',
        'datum': 'MLLW',
        'station': '8517921',
        'time_zone': 'lst_ldt',
        'units': 'metric',
        'interval': 'hilo',
        'format': 'json',
        'begin_date': begin_date,
        'end_date': end_date
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()
    df = pd.DataFrame(data['predictions'])

    # Parse timestamps and convert tide heights to numeric
    df['t'] = pd.to_datetime(df['t'])
    df['v'] = pd.to_numeric(df['v'])

    df = df.rename(columns={'t': 'datetime', 'v': 'prediction_in_meters'})

    df.to_csv(dir_this_data / f'tide_predictions_{begin_date}_to_{end_date}.csv', index=False)
