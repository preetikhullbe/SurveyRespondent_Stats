import pandas as pd
import numpy as np

# Load data only once here
df = pd.read_parquet('newclientandsupplier.parquet')

def process_data(output_file, start_date=None, end_date=None, client_filter=None):
    filtered_df = df.copy()

    # Apply Date filters if provided
    if start_date:
        filtered_df = filtered_df[filtered_df['Survey_EndDate'] >= pd.to_datetime(start_date)]
    if end_date:
        filtered_df = filtered_df[filtered_df['Survey_EndDate'] <= pd.to_datetime(end_date)]

    # Apply Client filter if provided
    if client_filter:
        filtered_df = filtered_df[filtered_df['client'].str.contains(client_filter, case=False, na=False)]

    # Define mappings
    client_start_statuses = [1, 2, 3, 4, 5, 8, 9, 22, 23, 25, 26]
    filtered_df['is_client_start'] = filtered_df['RespondentStatus'].isin(client_start_statuses)
    filtered_df['is_complete'] = filtered_df['RespondentStatus'] == 1

    # -------------------- Client Aggregation --------------------
    client_summary = filtered_df.groupby('client').agg(
        Client_Total_Starts=('RespondentStatus', 'count'),
        Client_Client_Starts=('is_client_start', 'sum'),
        Client_Completes=('is_complete', 'sum')
    ).reset_index()

    client_summary['Client_Conversion'] = (client_summary['Client_Completes'] / client_summary['Client_Total_Starts'] * 100).round(2)

    filtered_clients = client_summary[
        (client_summary['Client_Total_Starts'] > 2000) &
        (client_summary['Client_Client_Starts'] < 0.4 * client_summary['Client_Total_Starts'])
    ]

    # -------------------- Supplier Aggregation --------------------
    supplier_summary = filtered_df[filtered_df['client'].isin(filtered_clients['client'])].groupby(['client', 'supplier']).agg(
        Supplier_Total_Starts=('RespondentStatus', 'count'),
        Supplier_Client_Starts=('is_client_start', 'sum'),
        Supplier_Completes=('is_complete', 'sum')
    ).reset_index()

    supplier_summary['Supplier_Conversion'] = (supplier_summary['Supplier_Completes'] / supplier_summary['Supplier_Total_Starts'] * 100).round(2)

    supplier_filtered = supplier_summary[
        (supplier_summary['Supplier_Total_Starts'] > 500) & 
        (supplier_summary['Supplier_Conversion'] < 3)
    ].copy()

    # -------------------- Dropout Aggregation --------------------
    dropouts = filtered_df[filtered_df['RespondentStatusName'].notnull()]
    dropout_counts = dropouts.groupby(['client', 'supplier', 'RespondentStatusName']).size().reset_index(name='Drop_Count')

    dropout_counts = dropout_counts.merge(
        supplier_filtered[['client', 'supplier', 'Supplier_Total_Starts']],
        on=['client', 'supplier'],
        how='inner'
    )

    dropout_counts['Drop_Percent'] = (dropout_counts['Drop_Count'] / dropout_counts['Supplier_Total_Starts'] * 100).round(2)

    dropout_counts = dropout_counts.sort_values(['client', 'supplier', 'Drop_Count'], ascending=[True, True, False])
    top_dropouts = dropout_counts.groupby(['client', 'supplier']).head(4)
    top_dropouts = top_dropouts[~top_dropouts['RespondentStatusName'].isin(['Start', 'Complete'])]

    # -------------------- Qualification Aggregation --------------------
    demo_df = filtered_df[filtered_df['RespondentStatusName'] == 'DemoTerminate']
    qualification_counts = demo_df.groupby(['client', 'supplier', 'QualificationName']).size().reset_index(name='Qualification_Count')

    demo_total = demo_df.groupby(['client', 'supplier']).size().reset_index(name='Total_DemoTerminate')
    qualification_counts = qualification_counts.merge(demo_total, on=['client', 'supplier'], how='left')
    qualification_counts['Qualification_Percent'] = (qualification_counts['Qualification_Count'] / qualification_counts['Total_DemoTerminate'] * 100).round(2)

    qualification_counts = qualification_counts.sort_values(['client', 'supplier', 'Qualification_Count'], ascending=[True, True, False])
    top_qualifications = qualification_counts.groupby(['client', 'supplier']).head(3)

    # -------------------- Merge Dropouts Only --------------------
    final = supplier_filtered.merge(
        filtered_clients[['client', 'Client_Total_Starts', 'Client_Client_Starts', 'Client_Conversion']],
        on='client',
        how='left'
    ).merge(
        top_dropouts,
        on=['client', 'supplier'],
        how='left'
    )

    final.rename(columns={
        'client': 'Client',
        'supplier': 'Supplier',
        'Client_Total_Starts': 'Starts(client)',
        'Client_Client_Starts': 'Client Starts',
        'Client_Conversion': 'Conversion(client)',
        'Supplier_Total_Starts_x': 'Starts(supplier)',
        'Supplier_Client_Starts': 'Client Starts(supplier)',
        'Supplier_Conversion': 'Conversion(supplier)',
        'RespondentStatusName': 'Respondent Status',
        'Drop_Count': 'Count',
        'Drop_Percent': 'Percentage'
    }, inplace=True)

    final = final[[ 'Client', 'Starts(client)', 'Client Starts', 'Conversion(client)',
        'Supplier', 'Starts(supplier)', 'Client Starts(supplier)', 'Conversion(supplier)',
        'Respondent Status', 'Count', 'Percentage']]

    # -------------------- Export to Excel (with logic fix applied) --------------------
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        final.to_excel(writer, index=False, sheet_name='Report')
        workbook = writer.book
        worksheet = writer.sheets['Report']

        header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        cell_format = workbook.add_format({'valign': 'vcenter', 'border': 1})

        for col_num, value in enumerate(final.columns.values):
            worksheet.write(0, col_num, value, header_format)

        worksheet.write(0, len(final.columns), 'Qualification Name', header_format)
        worksheet.write(0, len(final.columns)+1, 'Qualification Percentage', header_format)
        worksheet.set_column('A:O', 18)

        start_row = 1
        for client, client_df in final.groupby('Client'):
            client_rows = 0
            supplier_start_row = start_row
            for supplier, supplier_df in client_df.groupby('Supplier'):
                other_rows = supplier_df[supplier_df['Respondent Status'] != 'DemoTerminate'].shape[0]
                demo_row = supplier_df[supplier_df['Respondent Status'] == 'DemoTerminate']
                if not demo_row.empty:
                    quals = top_qualifications[
                        (top_qualifications['client'] == client) & 
                        (top_qualifications['supplier'] == supplier)]
                    qual_rows = max(len(quals), 1)
                else:
                    qual_rows = 0

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
                            worksheet.write(supplier_start_row + i, 11, qual_row['QualificationName'], cell_format)
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


