import pandas as pd
import numpy as np

def process_data(df, output_file, start_date=None, end_date=None, client_filter=None):
    filtered_df = df.copy()

    # Ensure required columns are present
    expected_cols = ['survey_enddate', 'clientname', 'suppliername',
                     'respondentstatusid', 'respondentstatus', 'qualificationname']
    missing_cols = [col for col in expected_cols if col not in filtered_df.columns]
    if missing_cols:
        raise ValueError(f"Missing expected columns in data: {missing_cols}")

    # Ensure survey_enddate is datetime
    #filtered_df['survey_enddate'] = pd.to_datetime(filtered_df['survey_enddate'], errors='coerce')

    ignored_status_ids = [1, 3, 7, 15, 26]
    # Apply date filters
    if start_date:
        filtered_df = filtered_df[filtered_df['survey_enddate'] >= pd.to_datetime(start_date)]
    if end_date:
        filtered_df = filtered_df[filtered_df['survey_enddate'] <= pd.to_datetime(end_date)]

    if client_filter:
        filtered_df = filtered_df[filtered_df['clientname'].isin(client_filter)]

    client_start_statuses = [1, 2, 3, 4, 5, 8, 9, 22, 23, 25, 26]
    filtered_df['is_client_start'] = filtered_df['respondentstatusid'].isin(client_start_statuses)
    filtered_df['is_complete'] = filtered_df['respondentstatusid'] == 1
    filtered_df['is_other_status'] = ~filtered_df['respondentstatusid'].isin(ignored_status_ids)

    # Client Aggregation
    client_summary = filtered_df.groupby('clientname').agg(
        Client_Total_Starts=('respondentstatusid', 'count'),
        Client_Client_Starts=('is_client_start', 'sum'),
        Client_Completes=('is_complete', 'sum')
    ).reset_index()

    client_other_status = filtered_df.groupby('clientname')['is_other_status'].mean().mul(100).reset_index(name='other_status_rate')
    client_summary = client_summary.merge(client_other_status, on='clientname', how='left')

    client_summary['Client_Conversion'] = (client_summary['Client_Completes'] / client_summary['Client_Total_Starts'] * 100).round(2)

    filtered_clients = client_summary[
        (client_summary['Client_Total_Starts'] > 2000) &
        (
            (client_summary['Client_Client_Starts'] < 0.5 * client_summary['Client_Total_Starts']) |
            (client_summary['other_status_rate'] >= 20)
        )
    ]

    # Supplier Aggregation
    supplier_summary = filtered_df[filtered_df['clientname'].isin(filtered_clients['clientname'])].groupby(['clientname', 'suppliername']).agg(
        Supplier_Total_Starts=('respondentstatusid', 'count'),
        Supplier_Client_Starts=('is_client_start', 'sum'),
        Supplier_Completes=('is_complete', 'sum')
    ).reset_index()

    supplier_summary['Supplier_Conversion'] = (supplier_summary['Supplier_Completes'] / supplier_summary['Supplier_Total_Starts'] * 100).round(2)
    supplier_other_status = filtered_df.groupby(['clientname', 'suppliername'])['is_other_status'].mean().mul(100).reset_index(name='supplier_other_status_rate')
    supplier_summary = supplier_summary.merge(supplier_other_status, on=['clientname', 'suppliername'], how='left')

    supplier_filtered = supplier_summary[
        (supplier_summary['Supplier_Total_Starts'] > 500) &
        (
            (supplier_summary['Supplier_Conversion'] < 3) |
            (supplier_summary['supplier_other_status_rate'] >= 25)
        )
    ].copy()

    # Dropout Aggregation
    dropouts = filtered_df[filtered_df['respondentstatus'].notnull()]
    dropout_counts = dropouts.groupby(['clientname', 'suppliername', 'respondentstatus']).size().reset_index(name='Drop_Count')

    dropout_counts = dropout_counts.merge(
        supplier_filtered[['clientname', 'suppliername', 'Supplier_Total_Starts']],
        on=['clientname', 'suppliername'],
        how='inner'
    )

    dropout_counts['Drop_Percent'] = (dropout_counts['Drop_Count'] / dropout_counts['Supplier_Total_Starts'] * 100).round(2)
    dropout_counts = dropout_counts[~dropout_counts['respondentstatus'].isin([
        'Client Terminate', 'Client No Survey', 'Complete', 'Duplicate User', 'Duplicate IP'
    ])]

    dropout_counts = dropout_counts.sort_values(['clientname', 'suppliername', 'Drop_Count'], ascending=[True, True, False])
    top_dropouts = dropout_counts.groupby(['clientname', 'suppliername']).head(3)

    # Qualification Aggregation
    demo_df = filtered_df[filtered_df['respondentstatus'] == 'DemoTerminate']
    qualification_counts = demo_df.groupby(['clientname', 'suppliername', 'qualificationname']).size().reset_index(name='Qualification_Count')

    demo_total = demo_df.groupby(['clientname', 'suppliername']).size().reset_index(name='Total_DemoTerminate')
    qualification_counts = qualification_counts.merge(demo_total, on=['clientname', 'suppliername'], how='left')
    qualification_counts['Qualification_Percent'] = (qualification_counts['Qualification_Count'] / qualification_counts['Total_DemoTerminate'] * 100).round(2)

    qualification_counts = qualification_counts.sort_values(['clientname', 'suppliername', 'Qualification_Count'], ascending=[True, True, False])
    top_qualifications = qualification_counts.groupby(['clientname', 'suppliername']).head(3)

    # Merge Dropouts
    final = supplier_filtered.merge(
        filtered_clients[['clientname', 'Client_Total_Starts', 'Client_Client_Starts', 'Client_Conversion']],
        on='clientname', how='left'
    ).merge(
        top_dropouts,
        on=['clientname', 'suppliername'],
        how='left'
    )

    for col in ['respondentstatus', 'Drop_Count', 'Drop_Percent']:
        if col not in final.columns:
            final[col] = np.nan

    final.rename(columns={
        'clientname': 'Client',
        'suppliername': 'Supplier',
        'Client_Total_Starts': 'Starts(client)',
        'Client_Client_Starts': 'Client Starts',
        'Client_Conversion': 'Conversion(client)',
        'Supplier_Total_Starts_x': 'Starts(supplier)',
        'Supplier_Client_Starts': 'Client Starts(supplier)',
        'Supplier_Conversion': 'Conversion(supplier)',
        'respondentstatus': 'Respondent Status',
        'Drop_Count': 'Count',
        'Drop_Percent': 'Percentage'
    }, inplace=True)

    print("Final columns available:", final.columns.tolist())

    final = final[['Client', 'Starts(client)', 'Client Starts', 'Conversion(client)',
                   'Supplier', 'Starts(supplier)', 'Client Starts(supplier)', 'Conversion(supplier)',
                   'Respondent Status', 'Count', 'Percentage']]

    final = final.sort_values(by=['Starts(client)', 'Starts(supplier)'], ascending=[False, False])

    # Export
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        final.to_excel(writer, index=False, sheet_name='Report')
        workbook = writer.book
        worksheet = writer.sheets['Report']

        header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        cell_format = workbook.add_format({'valign': 'vcenter', 'border': 1})

        for col_num, value in enumerate(final.columns.values):
            worksheet.write(0, col_num, value, header_format)

        worksheet.write(0, len(final.columns), 'Qualification Name', header_format)
        worksheet.write(0, len(final.columns) + 1, 'Qualification Percentage', header_format)
        worksheet.set_column('A:O', 18)

        start_row = 1
        for client, client_df in final.groupby('Client', sort=False):
            client_rows = 0
            supplier_start_row = start_row
            for supplier, supplier_df in client_df.groupby('Supplier', sort=False):
                other_rows = supplier_df[supplier_df['Respondent Status'] != 'DemoTerminate'].shape[0]
                demo_row = supplier_df[supplier_df['Respondent Status'] == 'DemoTerminate']
                quals = top_qualifications[(top_qualifications['clientname'] == client) & (top_qualifications['suppliername'] == supplier)]
                qual_rows = max(len(quals), 1) if not demo_row.empty else 0
                total_supplier_rows = other_rows + qual_rows
                client_rows += total_supplier_rows

                worksheet.merge_range(supplier_start_row, 4, supplier_start_row + total_supplier_rows - 1, 4, supplier, cell_format)
                worksheet.merge_range(supplier_start_row, 5, supplier_start_row + total_supplier_rows - 1, 5, supplier_df['Starts(supplier)'].iloc[0], cell_format)
                worksheet.merge_range(supplier_start_row, 6, supplier_start_row + total_supplier_rows - 1, 6, supplier_df['Client Starts(supplier)'].iloc[0], cell_format)
                worksheet.merge_range(supplier_start_row, 7, supplier_start_row + total_supplier_rows - 1, 7, supplier_df['Conversion(supplier)'].iloc[0], cell_format)

                for _, row in supplier_df[supplier_df['Respondent Status'] != 'DemoTerminate'].iterrows():
                    worksheet.write(supplier_start_row, 8, row['Respondent Status'], cell_format)
                    worksheet.write(supplier_start_row, 9, row['Count'], cell_format)
                    worksheet.write(supplier_start_row, 10, row['Percentage'], cell_format)
                    worksheet.write(supplier_start_row, 11, '', cell_format)
                    worksheet.write(supplier_start_row, 12, '', cell_format)
                    supplier_start_row += 1

                if not demo_row.empty:
                    demo_data = demo_row.iloc[0]
                    worksheet.merge_range(supplier_start_row, 8, supplier_start_row + qual_rows - 1, 8, demo_data['Respondent Status'], cell_format)
                    worksheet.merge_range(supplier_start_row, 9, supplier_start_row + qual_rows - 1, 9, demo_data['Count'], cell_format)
                    worksheet.merge_range(supplier_start_row, 10, supplier_start_row + qual_rows - 1, 10, demo_data['Percentage'], cell_format)

                    if not quals.empty:
                        for i, (_, qual_row) in enumerate(quals.iterrows()):
                            worksheet.write(supplier_start_row + i, 11, qual_row['qualificationname'], cell_format)
                            worksheet.write(supplier_start_row + i, 12, qual_row['Qualification_Percent'], cell_format)
                    else:
                        worksheet.write(supplier_start_row, 11, '', cell_format)
                        worksheet.write(supplier_start_row, 12, '', cell_format)

                    supplier_start_row += qual_rows

            worksheet.merge_range(start_row, 0, start_row + client_rows - 1, 0, client, cell_format)
            worksheet.merge_range(start_row, 1, start_row + client_rows - 1, 1, client_df['Starts(client)'].iloc[0], cell_format)
            worksheet.merge_range(start_row, 2, start_row + client_rows - 1, 2, client_df['Client Starts'].iloc[0], cell_format)
            worksheet.merge_range(start_row, 3, start_row + client_rows - 1, 3, client_df['Conversion(client)'].iloc[0], cell_format)

            start_row += client_rows

    print("✅ Fully Correct Report Generated!")
