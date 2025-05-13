from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, timedelta, time
import pytz
import pandas as pd
from io import BytesIO, StringIO
import csv

app = Flask(__name__)

def convert_local_to_utc(date_time, tz_name):
    local_tz = pytz.timezone(tz_name)
    if isinstance(date_time, datetime):
        local_dt = local_tz.localize(date_time, is_dst=None)
    else:
        naive = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
        local_dt = local_tz.localize(naive, is_dst=None)
    return local_dt.astimezone(pytz.utc)

def process_single_row(input_data):
    try:
        entry_level = int(input_data.get('entry_level', 0))
        apat_default_effective_days = int(input_data.get('apat_default_effective_days', 6))
        apat_effective_days = int(input_data.get('apat_effective_days', 2))
        timez = input_data.get('timezone', 'CET')
        apat_pricing_closer_days = int(input_data.get('apat_pricing_closer_days', 4))
        apat_pricing_closer_time_str = input_data.get('apat_pricing_closer_time', '23:59:59')
        cut_off_time = input_data.get('cut_off_time', '13:00:00')
        start_input = input_data.get('start_date', '2025-05-06 00:00:00')

        output = []

        if entry_level == 0:
            start_dt = datetime.strptime(start_input, '%Y-%m-%d %H:%M:%S')
            utc_final_sub_time = convert_local_to_utc(start_dt, timez) + timedelta(days=apat_pricing_closer_days)

            og_start_date = convert_local_to_utc(datetime.combine(start_dt.date(), time(0, 0, 0)), timez)
            og_convered_time = og_start_date.time()

            dt_str = f"{start_dt.date()} {apat_pricing_closer_time_str}"
            local_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            max_sub_time = convert_local_to_utc(local_dt, timez)

            end_dt = start_dt + timedelta(days=apat_pricing_closer_days)
            apat_pricing_closer_dt = datetime.combine(end_dt.date(), og_convered_time)

            batch_date = datetime.combine(start_dt.date() + timedelta(days=apat_pricing_closer_days), max_sub_time.time()) + timedelta(seconds=1)
            min_sub_datetime = convert_local_to_utc(datetime.combine(start_dt.date(), time(0, 0, 0)), timez).replace(tzinfo=None)
            max_sub_datetime = datetime.combine(start_dt.date() + timedelta(days=apat_pricing_closer_days), max_sub_time.time())

            min_effective_date = datetime.combine(start_dt.date() + timedelta(days=apat_default_effective_days), time(0, 0, 0))
            max_effective_date = datetime.combine(apat_pricing_closer_dt.date() + timedelta(days=apat_effective_days), time(0, 0, 0))

            output.append({
                "Batch Date": str(batch_date),
                "Min Submission": str(min_sub_datetime),
                "Max Submission": str(max_sub_datetime),
                "Min Effective": str(min_effective_date),
                "Max Effective": str(max_effective_date)
            })

        else:
            start_dt = datetime.strptime(start_input, '%Y-%m-%d %H:%M:%S')
            og_start_date = start_dt.date()

            start_dt_conv_str = f"{og_start_date} {apat_pricing_closer_time_str}"
            local_dt_st_dt = datetime.strptime(start_dt_conv_str, "%Y-%m-%d %H:%M:%S")
            utc_final_sub_time = convert_local_to_utc(local_dt_st_dt, timez) + timedelta(days=apat_pricing_closer_days)

            dt_str = f"{og_start_date} {cut_off_time}"
            local_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            cut_off_time_conv = convert_local_to_utc(local_dt, timez)

            start_dt = datetime.combine(og_start_date, utc_final_sub_time.time()).replace(tzinfo=None)
            end_dt = start_dt + timedelta(days=apat_pricing_closer_days)

            final_condition = False
            first_min_sub = None
            prev_batch = None
            entry_created = True

            while not final_condition:
                if start_dt.date() > end_dt.date():
                    if utc_final_sub_time.time() > cut_off_time_conv.time():
                        batch_date = datetime.combine(start_dt.date() - timedelta(days=1), utc_final_sub_time.time()).replace(tzinfo=None) + timedelta(seconds=1)
                        min_sub_datetime = prev_batch
                        max_sub_datetime = datetime.combine(start_dt.date() - timedelta(days=1), cut_off_time_conv.time()) - timedelta(seconds=1)
                        min_effective_date = datetime.combine(start_dt.date() + timedelta(days=1), time(0, 0, 0))
                    else:
                        entry_created = False
                    final_condition = True
                else:
                    batch_date = datetime.combine(start_dt.date(), cut_off_time_conv.time()).replace(tzinfo=None)
                    if start_dt.date() != end_dt.date() and not first_min_sub:
                        min_sub_datetime = convert_local_to_utc(datetime.combine(start_dt.date(), time(0, 0, 0)), timez).replace(tzinfo=None)
                        first_min_sub = min_sub_datetime
                    else:
                        min_sub_datetime = prev_batch
                    prev_batch = batch_date

                    max_sub_datetime = datetime.combine(start_dt.date(), cut_off_time_conv.time()).replace(tzinfo=None) - timedelta(seconds=1)
                    min_effective_date = datetime.combine(start_dt.date() + timedelta(days=1), time(0, 0, 0))

                    start_dt += timedelta(days=1)

                max_effective_date = min_effective_date if entry_level == 2 else datetime.combine(end_dt.date() + timedelta(days=apat_effective_days), time(0, 0, 0))

                if entry_created:
                    output.append({
                        "Batch Date": str(batch_date),
                        "Min Submission": str(min_sub_datetime),
                        "Max Submission": str(max_sub_datetime),
                        "Min Effective": str(min_effective_date),
                        "Max Effective": str(max_effective_date)
                    })

        return output
    except Exception as e:
        print(f"Error processing row: {str(e)}")
        return []

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Handle CSV upload
        if 'csv_file' in request.files:
            csv_file = request.files['csv_file']
            if csv_file.filename.endswith('.csv'):
                try:
                    # Read CSV data
                    stream = StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
                    csv_input = csv.DictReader(stream)
                    
                    # Create Excel file in memory
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        workbook = writer.book
                        
                        # Format for headers
                        header_format = workbook.add_format({
                            'bold': True,
                            'text_wrap': True,
                            'valign': 'top',
                            'fg_color': '#D7E4BC',
                            'border': 1
                        })
                        
                        # Process each row
                        for idx, row in enumerate(csv_input, 1):
                            results = process_single_row(row)
                            if not results:
                                continue
                                
                            sheet_name = f"Case_{idx}"
                            
                            # Create DataFrames
                            input_df = pd.DataFrame([row])
                            results_df = pd.DataFrame(results)
                            
                            # Write to Excel
                            input_df.to_excel(
                                writer,
                                sheet_name=sheet_name,
                                index=False,
                                startrow=0
                            )
                            
                            results_df.to_excel(
                                writer,
                                sheet_name=sheet_name,
                                index=False,
                                startrow=len(input_df) + 3  # Add some spacing
                            )
                            
                            # Apply formatting
                            worksheet = writer.sheets[sheet_name]
                            
                            # Format input header
                            worksheet.set_row(0, None, header_format)
                            
                            # Format results header
                            results_header_row = len(input_df) + 3
                            worksheet.set_row(results_header_row, None, header_format)
                            
                            # Add labels
                            worksheet.write(len(input_df) + 1, 0, "Results:")
                            
                            # Auto-adjust column widths
                            for i, col in enumerate(input_df.columns):
                                max_len = max((
                                    input_df[col].astype(str).map(len).max(),
                                    len(str(col))
                                )) + 2
                                worksheet.set_column(i, i, max_len)
                            
                            for i, col in enumerate(results_df.columns):
                                max_len = max((
                                    results_df[col].astype(str).map(len).max(),
                                    len(str(col))
                                )) + 2
                                worksheet.set_column(i, i, max_len)
                    
                    output.seek(0)
                    return send_file(
                        output,
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        as_attachment=True,
                        download_name='batch_results.xlsx'
                    )
                except Exception as e:
                    return jsonify({'error': f'Error processing CSV: {str(e)}'}), 400
            return jsonify({'error': 'Please upload a CSV file'}), 400
        
        # Handle single form submission
        try:
            form_data = request.form.to_dict()
            results = process_single_row(form_data)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(results)
            
            return render_template('index.html', results=results)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': str(e)}), 400
            return render_template('index.html', error=str(e))
    
    return render_template('index.html')

