import duro, gowanus_superfund, noaa, write_to_db

if __name__ == '__main__':
    df_gowanus_superfund = gowanus_superfund.get_data(
        pdf_name='RTA2-WQM-Weekly-Report_Week-098.pdf',
        url_date='2026/05',
        first_page_number=15
    )
    write_to_db.write_df_to_table(
        df = df_gowanus_superfund,
        table_name = 'turbidity_rta1',
        pk_cols = ['date', 'time']
    )