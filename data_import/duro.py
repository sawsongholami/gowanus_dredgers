import pandas as pd
import pathlib as pl

dir_this_data = pl.Path(__file__).parent.parent.absolute() / 'data' / 'duro'
dir_this_data.mkdir(exist_ok=True)

date = '01-02-24'


def get_data():
    df = pd.read_csv(dir_this_data / f'{date}.csv')
    df.columns = (df.columns
                  .str.lower()
                  .str.replace(' ', '_')
                  .str.replace('temperature', 'temp')
                  .str.lstrip('_'))
    df = (df
          .drop('longitude', axis=1)
          .rename(columns={'latitude': 'longitude'})
          .rename(columns={'date': 'latitude'})
          .rename(columns={'time': 'date'}))

    return df


if __name__ == '__main__':
    get_data()  # TODO
